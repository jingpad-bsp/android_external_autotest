# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re
import subprocess
import time
import xmlrpclib

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.cros import autoupdater
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.client.cros import constants
from autotest_lib.server import autoserv_parser
from autotest_lib.server import autotest
from autotest_lib.server import site_host_attributes
from autotest_lib.server.cros import servo
from autotest_lib.server.hosts import remote
from autotest_lib.site_utils.rpm_control_system import rpm_client

# Importing frontend.afe.models requires a full Autotest
# installation (with the Django modules), not just the source
# repository.  Most developers won't have the full installation, so
# the imports below will fail for them.
#
# The fix is to catch import exceptions, and set `models` to `None`
# on failure.  This has the side effect that
# SiteHost._get_board_from_afe() will fail:  That will manifest as
# failures during Repair jobs leaving the DUT as "Repair Failed".
# In practice, you can't test Repair jobs without a full
# installation, so that kind of failure isn't expected.
try:
    from autotest_lib.frontend import setup_django_environment
    from autotest_lib.frontend.afe import models
except:
    models = None


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


def add_function_to_list(functions_list):
    """Decorator used to group functions together into the provided list."""
    def add_func(func):
        functions_list.append(func)
        return func
    return add_func


class SiteHost(remote.RemoteHost):
    """Chromium OS specific subclass of Host."""

    _parser = autoserv_parser.autoserv_parser

    # Time to wait for new kernel to be marked successful after
    # auto update.
    _KERNEL_UPDATE_TIMEOUT = 120

    # Timeout values (in seconds) associated with various Chrome OS
    # state changes.
    #
    # In general, a good rule of thumb is that the timeout can be up
    # to twice the typical measured value on the slowest platform.
    # The times here have not necessarily been empirically tested to
    # meet this criterion.
    #
    # SLEEP_TIMEOUT:  Time to allow for suspend to memory.
    # RESUME_TIMEOUT: Time to allow for resume after suspend, plus
    #   time to restart the netwowrk.
    # BOOT_TIMEOUT: Time to allow for boot from power off.  Among
    #   other things, this must account for the 30 second dev-mode
    #   screen delay and time to start the network,
    # USB_BOOT_TIMEOUT: Time to allow for boot from a USB device,
    #   including the 30 second dev-mode delay and time to start the
    #   network,
    # SHUTDOWN_TIMEOUT: Time to allow for shut down.
    # REBOOT_TIMEOUT: Combination of shutdown and reboot times.
    # _INSTALL_TIMEOUT: Time to allow for chromeos-install.

    SLEEP_TIMEOUT = 2
    RESUME_TIMEOUT = 5
    BOOT_TIMEOUT = 45
    USB_BOOT_TIMEOUT = 150
    SHUTDOWN_TIMEOUT = 5
    REBOOT_TIMEOUT = SHUTDOWN_TIMEOUT + BOOT_TIMEOUT
    _INSTALL_TIMEOUT = 240

    _DEFAULT_SERVO_URL_FORMAT = ('/static/servo-images/'
                                 '%(board)s_test_image.bin')

    # TODO(jrbarnette):  Servo repair is restricted to x86-alex,
    # because the existing servo client code won't work on other
    # boards.  http://crosbug.com/36973
    _SERVO_REPAIR_WHITELIST = [ 'x86-alex' ]


    _RPM_RECOVERY_BOARDS = global_config.global_config.get_config_value('CROS',
            'rpm_recovery_boards', type=str).split(',')

    _MAX_POWER_CYCLE_ATTEMPTS = 6
    _LAB_MACHINE_FILE = '/mnt/stateful_partition/.labmachine'
    _RPM_HOSTNAME_REGEX = ('chromeos[0-9]+(-row[0-9]+)?-rack[0-9]+[a-z]*-'
                           'host[0-9]+')
    _LIGHTSENSOR_FILES = ['in_illuminance0_input',
                          'in_illuminance0_raw',
                          'illuminance0_input']
    _LIGHTSENSOR_SEARCH_DIR = '/sys/bus/iio/devices'
    _LABEL_FUNCTIONS = []


    @staticmethod
    def get_servo_arguments(arglist):
        servo_args = {}
        for arg in ('servo_host', 'servo_port'):
            if arg in arglist:
                servo_args[arg] = arglist[arg]
        return servo_args


    def _initialize(self, hostname, servo_args=None, *args, **dargs):
        """Initialize superclasses, and |self.servo|.

        For creating the host servo object, there are three
        possibilities:  First, if the host is a lab system known to
        have a servo board, we connect to that servo unconditionally.
        Second, if we're called from a control file that requires
        servo features for testing, it will pass settings for
        `servo_host`, `servo_port`, or both.  If neither of these
        cases apply, `self.servo` will be `None`.

        """
        super(SiteHost, self)._initialize(hostname=hostname,
                                          *args, **dargs)
        # self.env is a dictionary of environment variable settings
        # to be exported for commands run on the host.
        # LIBC_FATAL_STDERR_ can be useful for diagnosing certain
        # errors that might happen.
        self.env['LIBC_FATAL_STDERR_'] = '1'
        self._xmlrpc_proxy_map = {}
        self.servo = servo.Servo.get_lab_servo(hostname)
        if not self.servo and servo_args is not None:
            self.servo = servo.Servo(**servo_args)


    def machine_install(self, update_url=None, force_update=False,
                        local_devserver=False):
        if not update_url and self._parser.options.image:
            update_url = self._parser.options.image
        elif not update_url:
            raise autoupdater.ChromiumOSError(
                'Update failed. No update URL provided.')

        # In case the system is in a bad state, we always reboot the machine
        # before machine_install.
        self.reboot(timeout=60, wait=True)

        # Attempt to update the system.
        updater = autoupdater.ChromiumOSUpdater(update_url, host=self,
                                                local_devserver=local_devserver)
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

            update_engine_log = '/var/log/update_engine.log'
            logging.info('Dumping %s', update_engine_log)
            self.run('cat %s' % update_engine_log)
            # Updater has returned successfully; reboot the host.
            self.reboot(timeout=60, wait=True)
            # Touch the lab machine file to leave a marker that distinguishes
            # this image from other test images.
            self.run('touch %s' % self._LAB_MACHINE_FILE)

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

        # Clean up any old autotest directories which may be lying around.
        for path in global_config.global_config.get_config_value(
                'AUTOSERV', 'client_autodir_paths', type=list):
            self.run('rm -rf ' + path)


    def _get_board_from_afe(self):
        """Retrieve this host's board from its labels in the AFE.

        Looks for a host label of the form "board:<board>", and
        returns the "<board>" part of the label.  `None` is returned
        if there is not a single, unique label matching the pattern.

        @returns board from label, or `None`.
        """
        host_model = models.Host.objects.get(hostname=self.hostname)
        board_labels = filter(lambda l: l.name.startswith('board:'),
                              host_model.labels.all())
        board_name = None
        if len(board_labels) == 1:
            board_name = board_labels[0].name.split(':', 1)[1]
        elif len(board_labels) == 0:
            logging.error('Host %s does not have a board label.',
                          self.hostname)
        else:
            logging.error('Host %s has multiple board labels.',
                          self.hostname)
        return board_name


    def _servo_repair(self, board):
        """Attempt to repair this host using an attached Servo.

        Re-install the OS on the DUT by 1) installing a test image
        on a USB storage device attached to the Servo board,
        2) booting that image in recovery mode, and then
        3) installing the image.

        """
        server = dev_server.ImageServer.devserver_url_for_servo(board)
        image = server + (self._DEFAULT_SERVO_URL_FORMAT %
                          { 'board': board })
        self.servo.install_recovery_image(image)
        if not self.wait_up(timeout=self.USB_BOOT_TIMEOUT):
            raise error.AutoservError('DUT failed to boot from USB'
                                      ' after %d seconds' %
                                        self.USB_BOOT_TIMEOUT)
        self.run('chromeos-install --yes',
                 timeout=self._INSTALL_TIMEOUT)
        self.servo.power_long_press()
        self.servo.set('usb_mux_sel1', 'servo_sees_usbkey')
        self.servo.power_short_press()
        if not self.wait_up(timeout=self.BOOT_TIMEOUT):
            raise error.AutoservError('DUT failed to reboot installed '
                                      'test image after %d seconds' %
                                        self.BOOT_TIMEOUT)


    def _powercycle_to_repair(self):
        """Utilize the RPM Infrastructure to bring the host back up.

        If the host is not up/repaired after the first powercycle we utilize
        auto fallback to the last good install by powercycling and rebooting the
        host 6 times.
        """
        logging.info('Attempting repair via RPM powercycle.')
        failed_cycles = 0
        self.power_cycle()
        while not self.wait_up(timeout=self.BOOT_TIMEOUT):
            failed_cycles += 1
            if failed_cycles >= self._MAX_POWER_CYCLE_ATTEMPTS:
                raise error.AutoservError('Powercycled host %s %d times; '
                                          'device did not come back online.' %
                                            (self.hostname, failed_cycles))
            self.power_cycle()
        if failed_cycles == 0:
            logging.info('Powercycling was successful first time.')
        else:
            logging.info('Powercycling was successful after %d failures.',
                         failed_cycles)


    def repair_full(self):
        """Repair a host for repair level NO_PROTECTION.

        This overrides the base class function for repair; it does
        not call back to the parent class, but instead offers a
        simplified implementation based on the capabilities in the
        Chrome OS test lab.

        Repair follows this sequence:
          1. If the DUT passes `self.verify()`, do nothing.
          2. If the DUT can be power-cycled via RPM, try to repair
             by power-cycling.

        As with the parent method, the last operation performed on
        the DUT must be to call `self.verify()`; if that call fails,
        the exception it raises is passed back to the caller.
        """
        try:
            self.verify()
        except:
            host_board = self._get_board_from_afe()
            if host_board is None:
                logging.error('host %s has no board; failing repair',
                              self.hostname)
                raise
            if (self.servo and
                    host_board in self._SERVO_REPAIR_WHITELIST):
                self._servo_repair(host_board)
            elif (self.has_power() and
                  host_board in self._RPM_RECOVERY_BOARDS):
                self._powercycle_to_repair()
            else:
                logging.error('host %s has no servo and no RPM control; '
                              'failing repair', self.hostname)
                raise
            self.verify()


    def close(self):
        super(SiteHost, self).close()
        self.xmlrpc_disconnect_all()


    def cleanup(self):
        client_at = autotest.Autotest(self)
        self.run('rm -f %s' % constants.CLEANUP_LOGS_PAUSED_FILE)
        try:
            client_at.run_static_method('autotest_lib.client.cros.cros_ui',
                                        '_clear_login_prompt_state')
            self.run('restart ui')
            client_at.run_static_method('autotest_lib.client.cros.cros_ui',
                                        '_wait_for_login_prompt')
        except error.AutotestRunError:
            logging.warn('Unable to restart ui, rebooting device.')
            # Since restarting the UI fails fall back to normal Autotest
            # cleanup routines, i.e. reboot the machine.
            super(SiteHost, self).cleanup()


    # TODO (sbasi) crosbug.com/35656
    # Renamed the sitehost cleanup method so we don't go down this pathway.
    # def cleanup(self):
    def cleanup_poweron(self):
        """Special cleanup method to make sure hosts always get power back."""
        super(SiteHost, self).cleanup()
        if self.has_power():
            try:
                self.power_on()
            except rpm_client.RemotePowerException:
                # If cleanup has completed but there was an issue with the RPM
                # Infrastructure, log an error message rather than fail cleanup
                logging.error('Failed to turn Power On for this host after '
                              'cleanup through the RPM Infrastructure.')


    def reboot(self, **dargs):
        """
        This function reboots the site host. The more generic
        RemoteHost.reboot() performs sync and sleeps for 5
        seconds. This is not necessary for Chrome OS devices as the
        sync should be finished in a short time during the reboot
        command.
        """
        if 'reboot_cmd' not in dargs:
            dargs['reboot_cmd'] = ('((reboot & sleep 10; reboot -f &)'
                                   ' </dev/null >/dev/null 2>&1 &)')
        # Enable fastsync to avoid running extra sync commands before reboot.
        if 'fastsync' not in dargs:
            dargs['fastsync'] = True
        super(SiteHost, self).reboot(**dargs)


    def verify_software(self):
        """Verify working software on a Chrome OS system.

        Tests for the following conditions:
         1. All conditions tested by the parent version of this
            function.
         2. Sufficient space in /mnt/stateful_partition.
         3. update_engine answers a simple status request over DBus.

        """
        super(SiteHost, self).verify_software()
        self.check_diskspace(
            '/mnt/stateful_partition',
            global_config.global_config.get_config_value(
                'SERVER', 'gb_diskspace_required', type=int,
                default=20))
        self.run('update_engine_client --status')


    def xmlrpc_connect(self, command, port, cleanup=None):
        """Connect to an XMLRPC server on the host.

        The `command` argument should be a simple shell command that
        starts an XMLRPC server on the given `port`.  The command
        must not daemonize, and must terminate cleanly on SIGTERM.
        The command is started in the background on the host, and a
        local XMLRPC client for the server is created and returned
        to the caller.

        Note that the process of creating an XMLRPC client makes no
        attempt to connect to the remote server; the caller is
        responsible for determining whether the server is running
        correctly, and is ready to serve requests.

        @param command Shell command to start the server.
        @param port Port number on which the server is expected to
                    be serving.
        """
        self.xmlrpc_disconnect(port)

        # Chrome OS on the target closes down most external ports
        # for security.  We could open the port, but doing that
        # would conflict with security tests that check that only
        # expected ports are open.  So, to get to the port on the
        # target we use an ssh tunnel.
        local_port = utils.get_unused_port()
        tunnel_options = '-n -N -q -L %d:localhost:%d' % (local_port, port)
        ssh_cmd = make_ssh_command(opts=tunnel_options)
        tunnel_cmd = '%s %s' % (ssh_cmd, self.hostname)
        logging.debug('Full tunnel command: %s', tunnel_cmd)
        tunnel_proc = subprocess.Popen(tunnel_cmd, shell=True, close_fds=True)
        logging.debug('Started XMLRPC tunnel, local = %d'
                      ' remote = %d, pid = %d',
                      local_port, port, tunnel_proc.pid)

        # Start the server on the host.  Redirection in the command
        # below is necessary, because 'ssh' won't terminate until
        # background child processes close stdin, stdout, and
        # stderr.
        remote_cmd = '( %s ) </dev/null >/dev/null 2>&1 & echo $!' % command
        remote_pid = self.run(remote_cmd).stdout.rstrip('\n')
        logging.debug('Started XMLRPC server on host %s, pid = %s',
                      self.hostname, remote_pid)

        self._xmlrpc_proxy_map[port] = (cleanup, tunnel_proc)
        rpc_url = 'http://localhost:%d' % local_port
        return xmlrpclib.ServerProxy(rpc_url, allow_none=True)


    def xmlrpc_disconnect(self, port):
        """Disconnect from an XMLRPC server on the host.

        Terminates the remote XMLRPC server previously started for
        the given `port`.  Also closes the local ssh tunnel created
        for the connection to the host.  This function does not
        directly alter the state of a previously returned XMLRPC
        client object; however disconnection will cause all
        subsequent calls to methods on the object to fail.

        This function does nothing if requested to disconnect a port
        that was not previously connected via `self.xmlrpc_connect()`

        @param port Port number passed to a previous call to
                    `xmlrpc_connect()`
        """
        if port not in self._xmlrpc_proxy_map:
            return
        entry = self._xmlrpc_proxy_map[port]
        remote_name = entry[0]
        tunnel_proc = entry[1]
        if remote_name:
            # We use 'pkill' to find our target process rather than
            # a PID, because the host may have rebooted since
            # connecting, and we don't want to kill an innocent
            # process with the same PID.
            #
            # 'pkill' helpfully exits with status 1 if no target
            # process  is found, for which run() will throw an
            # exception.  We don't want that, so we the ignore
            # status.
            self.run("pkill -f '%s'" % remote_name, ignore_status=True)

        if tunnel_proc.poll() is None:
            tunnel_proc.terminate()
            logging.debug('Terminated tunnel, pid %d', tunnel_proc.pid)
        else:
            logging.debug('Tunnel pid %d terminated early, status %d',
                          tunnel_proc.pid, tunnel_proc.returncode)
        del self._xmlrpc_proxy_map[port]


    def xmlrpc_disconnect_all(self):
        """Disconnect all known XMLRPC proxy ports."""
        for port in self._xmlrpc_proxy_map.keys():
            self.xmlrpc_disconnect(port)


    def _ping_is_up(self):
        """Ping the host once, and return whether it responded."""
        return utils.ping(self.hostname, tries=1, deadline=1) == 0


    def ping_wait_down(self, timeout):
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
        if not self.ping_wait_down(timeout=self.SLEEP_TIMEOUT):
            raise error.TestFail(
                'client failed to sleep after %d seconds' %
                    self.SLEEP_TIMEOUT)


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
        if not self.wait_up(timeout=self.RESUME_TIMEOUT):
            raise error.TestFail(
                'client failed to resume from sleep after %d seconds' %
                    self.RESUME_TIMEOUT)
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
        if not self.ping_wait_down(timeout=self.SHUTDOWN_TIMEOUT):
            raise error.TestFail(
                'client failed to shut down after %d seconds' %
                    self.SHUTDOWN_TIMEOUT)


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
        if not self.wait_up(timeout=self.REBOOT_TIMEOUT):
            raise error.TestFail(
                'client failed to reboot after %d seconds' %
                    self.REBOOT_TIMEOUT)
        elif old_boot_id:
            if self.get_boot_id() == old_boot_id:
                raise error.TestFail(
                    'client is back up, but did not reboot'
                    ' (boot %s)' % old_boot_id)


    @staticmethod
    def check_for_rpm_support(hostname):
        """For a given hostname, return whether or not it is powered by an RPM.

        @return None if this host does not follows the defined naming format
                for RPM powered DUT's in the lab. If it does follow the format,
                it returns a regular expression MatchObject instead.
        """
        return re.match(SiteHost._RPM_HOSTNAME_REGEX, hostname)


    def has_power(self):
        """For this host, return whether or not it is powered by an RPM.

        @return True if this host is in the CROS lab and follows the defined
                naming format.
        """
        return SiteHost.check_for_rpm_support(self.hostname)


    def power_off(self):
        rpm_client.set_power(self.hostname, 'OFF')


    def power_on(self):
        rpm_client.set_power(self.hostname, 'ON')


    def power_cycle(self):
        rpm_client.set_power(self.hostname, 'CYCLE')


    def get_platform(self):
        """Determine the correct platform label for this host.

        @returns a string representing this host's platform.
        """
        crossystem = utils.Crossystem(self)
        crossystem.init()
        # Extract fwid value and use the leading part as the platform id.
        # fwid generally follow the format of {platform}.{firmware version}
        # Example: Alex.X.YYY.Z or Google_Alex.X.YYY.Z
        platform = crossystem.fwid().split('.')[0].lower()
        # Newer platforms start with 'Google_' while the older ones do not.
        return platform.replace('google_', '')


    @add_function_to_list(_LABEL_FUNCTIONS)
    def get_board(self):
        """Determine the correct board label for this host.

        @returns a string representing this host's board.
        """
        release_info = utils.parse_cmd_output('cat /etc/lsb-release',
                                              run_method=self.run)
        board = release_info['CHROMEOS_RELEASE_BOARD']
        # Devices in the lab generally have the correct board name but our own
        # development devices have {board_name}-signed-{key_type}. The board
        # name may also begin with 'x86-' which we need to keep.
        if 'x86' not in board:
            return 'board:%s' % board.split('-')[0]
        return 'board:%s' % '-'.join(board.split('-')[0:2])


    @add_function_to_list(_LABEL_FUNCTIONS)
    def has_lightsensor(self):
        """Determine the correct board label for this host.

        @returns the string 'lightsensor' if this host has a lightsensor or
                 None if it does not.
        """
        search_cmd = "find -L %s -maxdepth 4 | egrep '%s'" % (
            self._LIGHTSENSOR_SEARCH_DIR, '|'.join(self._LIGHTSENSOR_FILES))
        try:
            # Run the search cmd following the symlinks. Stderr_tee is set to
            # None as there can be a symlink loop, but the command will still
            # execute correctly with a few messages printed to stderr.
            self.run(search_cmd, stdout_tee=None, stderr_tee=None)
            return 'lightsensor'
        except error.AutoservRunError:
            # egrep exited with a return code of 1 meaning none of the possible
            # lightsensor files existed.
            return None


    @add_function_to_list(_LABEL_FUNCTIONS)
    def has_bluetooth(self):
        """Determine the correct board label for this host.

        @returns the string 'bluetooth' if this host has bluetooth or
                 None if it does not.
        """
        try:
            self.run('test -d /sys/class/bluetooth/hci0')
            # test exited with a return code of 0.
            return 'bluetooth'
        except error.AutoservRunError:
            # test exited with a return code 1 meaning the directory did not
            # exist.
            return None


    def get_labels(self):
        """Return a list of labels for this given host.

        This is the main way to retrieve all the automatic labels for a host
        as it will run through all the currently implemented label functions.
        """
        labels = []
        for label_function in self._LABEL_FUNCTIONS:
            label = label_function(self)
            if label:
                labels.append(label)
        return labels
