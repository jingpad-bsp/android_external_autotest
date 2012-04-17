# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.cros import autoupdater
from autotest_lib.server import autoserv_parser
from autotest_lib.server import site_host_attributes
from autotest_lib.server import site_remote_power
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
    _KERNEL_UPDATE_TIMEOUT = 60

    # Ephemeral file to indicate that an update has just occurred.
    _JUST_UPDATED_FLAG = '/tmp/just_updated'

    def _initialize(self, hostname, *args, **dargs):
        super(SiteHost, self)._initialize(hostname=hostname,
                                          *args, **dargs)


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
