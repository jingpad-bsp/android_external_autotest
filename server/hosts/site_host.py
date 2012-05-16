# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import global_config, error
from autotest_lib.client.common_lib.cros import autoupdater
from autotest_lib.server import autoserv_parser
from autotest_lib.server import site_host_attributes
from autotest_lib.server import site_remote_power
from autotest_lib.server.cros import servo
from autotest_lib.server.hosts import remote


def make_ssh_command(user='root', port=22, opts='', hosts_file=None,
                     connect_timeout=None, alive_interval=None):
    """Override default make_ssh_command to use options tuned for Chrome OS.

    Tuning changes:
      - ConnectTimeout=30; maximum of 30 seconds allowed for an SSH connection
      failure.  Consistency with remote_access.sh.

      - ServerAliveInterval=180; which causes SSH to ping connection every
      180 seconds. In conjunction with ServerAliveCountMax ensures that if the
      connection dies, Autotest will bail out quickly. Originally tried 60 secs,
      but saw frequent job ABORTS where the test completed successfully.

      - ServerAliveCountMax=3; consistency with remote_access.sh.

      - ConnectAttempts=4; reduce flakiness in connection errors; consistency
      with remote_access.sh.

      - UserKnownHostsFile=/dev/null; we don't care about the keys. Host keys
      change with every new installation, don't waste memory/space saving them.

      - SSH protocol forced to 2; needed for ServerAliveInterval.
    """
    base_command = ('/usr/bin/ssh -a -x %s -o StrictHostKeyChecking=no'
                    ' -o UserKnownHostsFile=/dev/null -o BatchMode=yes'
                    ' -o ConnectTimeout=30 -o ServerAliveInterval=180'
                    ' -o ServerAliveCountMax=3 -o ConnectionAttempts=4'
                    ' -o Protocol=2 -l %s -p %d')
    return base_command % (opts, user, port)


class SiteHost(remote.RemoteHost):
    """Chromium OS specific subclass of Host."""

    _parser = autoserv_parser.autoserv_parser

    # Time to wait for new kernel to be marked successful.
    _KERNEL_UPDATE_TIMEOUT = 120

    # Ephemeral file to indicate that an update has just occurred.
    _JUST_UPDATED_FLAG = '/tmp/just_updated'

    # Timeout values used in test_wait_for_sleep(), et al.
    #
    # _RESUME_TIMEOUT has to be big enough to allow time for WiFi
    # reconnection.
    #
    # _REBOOT_TIMEOUT has to be big enough to allow time for the 30
    # second dev-mode screen delay _and_ time for network startup,
    # which takes several seconds longer than boot.
    #
    # TODO(jrbarnette):  None of these times have been thoroughly
    # tested empirically; if timeouts are a problem, increasing the
    # time limit really might be the right answer.
    _SLEEP_TIMEOUT = 2
    _RESUME_TIMEOUT = 5
    _SHUTDOWN_TIMEOUT = 5
    _REBOOT_TIMEOUT = 45


    def _initialize(self, hostname, require_servo=False, *args, **dargs):
        """Initialize superclasses, and |self.servo|.

        For creating the host servo object, there are three
        possibilities:  First, if the host is a lab system known to
        have a servo board, we connect to that servo unconditionally.
        Second, if we're called from a control file that requires
        servo features for testing, it will pass |require_servo| set
        to |True|, and we will start a local servod.  If neither of
        these cases apply, |self.servo| will be |None|.

        """
        super(SiteHost, self)._initialize(hostname=hostname,
                                          *args, **dargs)
        self.servo = servo.Servo.get_lab_servo(hostname)
        if not self.servo and require_servo:
            self.servo = servo.Servo()


    def machine_install(self, update_url=None, force_update=False):
        if not update_url and self._parser.options.image:
            update_url = self._parser.options.image
        elif not update_url:
            raise autoupdater.ChromiumOSError(
                'Update failed. No update URL provided.')

        # Attempt to update the system.
        updater = autoupdater.ChromiumOSUpdater(update_url, host=self)
        if updater.run_update(force_update):
            # Figure out active and inactive kernel.
            active_kernel, inactive_kernel = updater.get_kernel_state()

            # Ensure inactive kernel has higher priority than active.
            if (updater.get_kernel_priority(inactive_kernel)
                    < updater.get_kernel_priority(active_kernel)):
                raise autoupdater.ChromiumOSError(
                    'Update failed. The priority of the inactive kernel'
                    ' partition is less than that of the active kernel'
                    ' partition.')

            # Updater has returned, successfully, reboot the host.
            self.reboot(timeout=60, wait=True)

            # Following the reboot, verify the correct version.
            updater.check_version()

            # Figure out newly active kernel.
            new_active_kernel, _ = updater.get_kernel_state()

            # Ensure that previously inactive kernel is now the active kernel.
            if new_active_kernel != inactive_kernel:
                raise autoupdater.ChromiumOSError(
                    'Update failed. New kernel partition is not active after'
                    ' boot.')

            host_attributes = site_host_attributes.HostAttributes(self.hostname)
            if host_attributes.has_chromeos_firmware:
                # Wait until tries == 0 and success, or until timeout.
                utils.poll_for_condition(
                    lambda: (updater.get_kernel_tries(new_active_kernel) == 0
                             and updater.get_kernel_success(new_active_kernel)),
                    exception=autoupdater.ChromiumOSError(
                        'Update failed. Timed out waiting for system to mark'
                        ' new kernel as successful.'),
                    timeout=self._KERNEL_UPDATE_TIMEOUT, sleep_interval=5)

            # TODO(dalecurtis): Hack for R12 builds to make sure BVT runs of
            # platform_Shutdown pass correctly.
            if updater.update_version.startswith('0.12'):
                self.reboot(timeout=60, wait=True)

            # Mark host as recently updated. Hosts are rebooted at the end of
            # every test cycle which will remove the file.
            self.run('touch %s' % self._JUST_UPDATED_FLAG)

        # Clean up any old autotest directories which may be lying around.
        for path in global_config.global_config.get_config_value(
                'AUTOSERV', 'client_autodir_paths', type=list):
            self.run('rm -rf ' + path)


    def has_just_updated(self):
        """Indicates whether the host was updated within this boot."""
        # Check for the existence of the just updated flag file.
        return self.run(
            '[ -f %s ] && echo T || echo F'
            % self._JUST_UPDATED_FLAG).stdout.strip() == 'T'


    def cleanup(self):
        """Special cleanup method to make sure hosts always get power back."""
        super(SiteHost, self).cleanup()
        remote_power = site_remote_power.RemotePower(self.hostname)
        if remote_power:
            remote_power.set_power_on()


    def verify_software(self):
        """Ensure the stateful partition has space for Autotest and updates.

        Similar to what is done by AbstractSSH, except instead of checking the
        Autotest installation path, just check the stateful partition.

        Checking the stateful partition is preferable in case it has been wiped,
        resulting in an Autotest installation path which doesn't exist and isn't
        writable. We still want to pass verify in this state since the partition
        will be recovered with the next install.
        """
        super(SiteHost, self).verify_software()
        self.check_diskspace(
            '/mnt/stateful_partition',
            global_config.global_config.get_config_value(
                'SERVER', 'gb_diskspace_required', type=int,
                default=20))


    def _ping_is_up(self):
        """Ping the host once, and return whether it responded."""
        return utils.ping(self.hostname, tries=1, deadline=1) == 0


    def _ping_wait_down(self, timeout):
        """Wait until the host no longer responds to `ping`.

        @param timeout Minimum time to allow before declaring the
                       host to be non-responsive.
        """

        # This function is a slightly faster version of wait_down().
        #
        # In AbstractSSHHost.wait_down(), `ssh` is used to determine
        # whether the host is down.  In some situations (mine, at
        # least), `ssh` can take over a minute to determine that the
        # host is down.  The `ping` command answers the question
        # faster, so we use that here instead.
        #
        # There is no equivalent for wait_up(), because a target that
        # answers to `ping` won't necessarily respond to `ssh`.
        end_time = time.time() + timeout
        while time.time() <= end_time:
            if not self._ping_is_up():
                return True

        # If the timeout is short relative to the run time of
        # _ping_is_up(), we might be prone to false failures for
        # lack of checking frequently enough.  To be safe, we make
        # one last check _after_ the deadline.
        return not self._ping_is_up()


    def test_wait_for_sleep(self):
        """Wait for the client to enter low-power sleep mode.

        The test for "is asleep" can't distinguish a system that is
        powered off; to confirm that the unit was asleep, it is
        necessary to force resume, and then call
        `test_wait_for_resume()`.

        This function is expected to be called from a test as part
        of a sequence like the following:

        ~~~~~~~~
            boot_id = host.get_boot_id()
            # trigger sleep on the host
            host.test_wait_for_sleep()
            # trigger resume on the host
            host.test_wait_for_resume(boot_id)
        ~~~~~~~~

        @exception TestFail The host did not go to sleep within
                            the allowed time.
        """
        if not self._ping_wait_down(timeout=self._SLEEP_TIMEOUT):
            raise error.TestFail(
                'client failed to sleep after %d seconds' %
                    self._SLEEP_TIMEOUT)


    def test_wait_for_resume(self, old_boot_id):
        """Wait for the client to resume from low-power sleep mode.

        The `old_boot_id` parameter should be the value from
        `get_boot_id()` obtained prior to entering sleep mode.  A
        `TestFail` exception is raised if the boot id changes.

        See @ref test_wait_for_sleep for more on this function's
        usage.

        @param[in] old_boot_id A boot id value obtained before the
                               target host went to sleep.

        @exception TestFail The host did not respond within the
                            allowed time.
        @exception TestFail The host responded, but the boot id test
                            indicated a reboot rather than a sleep
                            cycle.
        """
        if not self.wait_up(timeout=self._RESUME_TIMEOUT):
            raise error.TestFail(
                'client failed to resume from sleep after %d seconds' %
                    self._RESUME_TIMEOUT)
        else:
            new_boot_id = self.get_boot_id()
            if new_boot_id != old_boot_id:
                raise error.TestFail(
                    'client rebooted, but sleep was expected'
                    ' (old boot %s, new boot %s)'
                        % (old_boot_id, new_boot_id))


    def test_wait_for_shutdown(self):
        """Wait for the client to shut down.

        The test for "has shut down" can't distinguish a system that
        is merely asleep; to confirm that the unit was down, it is
        necessary to force boot, and then call test_wait_for_boot().

        This function is expected to be called from a test as part
        of a sequence like the following:

        ~~~~~~~~
            boot_id = host.get_boot_id()
            # trigger shutdown on the host
            host.test_wait_for_shutdown()
            # trigger boot on the host
            host.test_wait_for_boot(boot_id)
        ~~~~~~~~

        @exception TestFail The host did not shut down within the
                            allowed time.
        """
        if not self._ping_wait_down(timeout=self._SHUTDOWN_TIMEOUT):
            raise error.TestFail(
                'client failed to shut down after %d seconds' %
                    self._SHUTDOWN_TIMEOUT)


    def test_wait_for_boot(self, old_boot_id=None):
        """Wait for the client to boot from cold power.

        The `old_boot_id` parameter should be the value from
        `get_boot_id()` obtained prior to shutting down.  A
        `TestFail` exception is raised if the boot id does not
        change.  The boot id test is omitted if `old_boot_id` is not
        specified.

        See @ref test_wait_for_shutdown for more on this function's
        usage.

        @param[in] old_boot_id A boot id value obtained before the
                               shut down.

        @exception TestFail The host did not respond within the
                            allowed time.
        @exception TestFail The host responded, but the boot id test
                            indicated that there was no reboot.
        """
        if not self.wait_up(timeout=self._REBOOT_TIMEOUT):
            raise error.TestFail(
                'client failed to reboot after %d seconds' %
                    self._REBOOT_TIMEOUT)
        elif old_boot_id:
            if self.get_boot_id() == old_boot_id:
                raise error.TestFail(
                    'client is back up, but did not reboot'
                    ' (boot %s)' % old_boot_id)
