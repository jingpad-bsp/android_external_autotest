# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import functools
import logging
import os
import re
import stat
import time

import common

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import retry
from autotest_lib.server import utils
from autotest_lib.server.cros.dynamic_suite import constants
from autotest_lib.server.hosts import abstract_ssh


ADB_CMD = 'adb'
FASTBOOT_CMD = 'fastboot'
SHELL_CMD = 'shell'
# Some devices have no serial, then `adb serial` has output such as:
# (no serial number)  device
# ??????????          device
DEVICE_NO_SERIAL_MSG = '(no serial number)'
DEVICE_NO_SERIAL_TAG = '<NO_SERIAL>'
# Regex to find an adb device. Examples:
# 0146B5580B01801B    device
# 018e0ecb20c97a62    device
# 172.22.75.141:5555  device
DEVICE_FINDER_REGEX = ('^(?P<SERIAL>([\w]+)|(\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3})|' +
                       re.escape(DEVICE_NO_SERIAL_MSG) +
                       ')([:]5555)?[ \t]+(?:device|fastboot)')
CMD_OUTPUT_PREFIX = 'ADB_CMD_OUTPUT'
CMD_OUTPUT_REGEX = ('(?P<OUTPUT>[\s\S]*)%s:(?P<EXIT_CODE>\d{1,3})' %
                    CMD_OUTPUT_PREFIX)
RELEASE_FILE = 'ro.build.version.release'
BOARD_FILE = 'ro.product.device'
TMP_DIR = '/data/local/tmp'
ANDROID_TESTER_FILEFLAG = '/mnt/stateful_partition/.android_tester'
# Regex to pull out file type, perms and symlink. Example:
# lrwxrwx--- 1 6 2015-09-12 19:21 blah_link -> ./blah
FILE_INFO_REGEX = '^(?P<TYPE>[dl-])(?P<PERMS>[rwx-]{9})'
FILE_SYMLINK_REGEX = '^.*-> (?P<SYMLINK>.+)'
# List of the perm stats indexed by the order they are listed in the example
# supplied above.
FILE_PERMS_FLAGS = [stat.S_IRUSR, stat.S_IWUSR, stat.S_IXUSR,
                    stat.S_IRGRP, stat.S_IWGRP, stat.S_IXGRP,
                    stat.S_IROTH, stat.S_IWOTH, stat.S_IXOTH]

# Default maximum number of seconds to wait for a device to be down.
DEFAULT_WAIT_DOWN_TIME_SECONDS = 10
# Default maximum number of seconds to wait for a device to be up.
DEFAULT_WAIT_UP_TIME_SECONDS = 30

class ADBHost(abstract_ssh.AbstractSSHHost):
    """This class represents a host running an ADB server."""

    _LABEL_FUNCTIONS = []
    _DETECTABLE_LABELS = []
    label_decorator = functools.partial(utils.add_label_detector,
                                        _LABEL_FUNCTIONS,
                                        _DETECTABLE_LABELS)


    @staticmethod
    def check_host(host, timeout=10):
        """
        Check if the given host is an adb host.

        @param host: An ssh host representing a device.
        @param timeout: The timeout for the run command.


        @return: True if the host device has adb.

        @raises AutoservRunError: If the command failed.
        @raises AutoservSSHTimeout: Ssh connection has timed out.
        """
        try:
            if not host.verify_ssh_user_access():
                host.user = 'adb'
            result = host.run(
                    'test -f %s' % ANDROID_TESTER_FILEFLAG,
                    timeout=timeout)
        except (error.AutoservRunError, error.AutoservSSHTimeout):
            return False
        return result.exit_status == 0


    # TODO(garnold) Remove the 'serials' argument once all clients are made to
    # not use it.
    def _initialize(self, hostname='localhost', serials=None,
                    adb_serial=None, fastboot_serial=None,
                    device_hostname=None, *args, **dargs):
        """Initialize an ADB Host.

        This will create an ADB Host. Hostname should always refer to the
        host machine connected to an android device. This will either be the
        only android device connected or if there are multiple, serial must be
        specified. Currently only one serial being passed in is supported.
        Multiple serial support will be coming soon (TODO(kevcheng)).  If
        device_hostname is supplied then all ADB commands will run over TCP/IP.

        @param hostname: Hostname of the machine running ADB.
        @param serials: DEPRECATED (to be removed)
        @param adb_serial: An ADB device serial. If None, assume a single
                           device is attached (and fail otherwise).
        @param fastboot_serial: A fastboot device serial. If None, defaults to
                                the ADB serial (or assumes a single device if
                                the latter is None).
        @param device_hostname: Hostname or IP of the android device we want to
                                interact with. If supplied all ADB interactions
                                run over TCP/IP.

        """
        if device_hostname and (adb_serial or fastboot_serial):
            raise error.AutoservError(
                    'TCP/IP and USB modes are mutually exclusive')

        self._num_of_boards = {}
        self._device_hostname = device_hostname
        self._use_tcpip = False
        self._local_adb = False
        self._adb_serial = adb_serial
        self._fastboot_serial = fastboot_serial or adb_serial

        msg ='Initializing ADB device on host: %s' % hostname
        if self._device_hostname:
            msg += ', device hostname: %s' % self._device_hostname
        if self._adb_serial:
            msg += ', ADB serial: %s' % self._adb_serial
        if self._fastboot_serial:
            msg += ', fastboot serial: %s' % self._fastboot_serial
        logging.debug(msg)

        if hostname == 'localhost':
            self._local_adb = True
        super(ADBHost, self)._initialize(hostname=hostname,
                                         is_client_install_supported=False,
                                         *args, **dargs)
        try:
            self.host_run('true')
        except error.AutoservRunError as e:
            # Some hosts may not have root access, in this case try user adb.
            logging.debug('Switching to user adb.')
            self.user = 'adb'

        self._connect_over_tcpip_as_needed()


    def _connect_over_tcpip_as_needed(self):
        """Connect to the ADB device over TCP/IP if so configured."""
        if not self._device_hostname:
            return
        logging.debug('Connecting to device over TCP/IP')
        if self._device_hostname in self.adb_devices():
            # We previously had a connection to this device, restart the ADB
            # server.
            self.adb_run('kill-server')
        # Ensure that connection commands don't run over TCP/IP.
        self._use_tcpip = False
        self.adb_run('tcpip 5555', timeout=10, ignore_timeout=True)
        time.sleep(2)
        try:
            self.adb_run('connect %s' % self._device_hostname)
        except (error.AutoservRunError, error.CmdError) as e:
            raise error.AutoservError('Failed to connect via TCP/IP: %s' % e)
        # Allow ADB a bit of time after connecting before interacting with the
        # device.
        time.sleep(5)
        # Switch back to using TCP/IP.
        self._use_tcpip = True


    # pylint: disable-msg=C0111
    def adb_run(self, command, shell=False, timeout=3600,
                ignore_status=False, ignore_timeout=False,
                stdout=utils.TEE_TO_LOGS, stderr=utils.TEE_TO_LOGS,
                connect_timeout=30, options='', stdin=None, verbose=True,
                args=()):
        """Runs an adb command.

        This command may launch on the adb device or on the adb host.

        Refer to _device_run method for docstring for parameters.
        """
        return self._device_run(
                ADB_CMD, command, shell, timeout, ignore_status,
                ignore_timeout, stdout, stderr, connect_timeout, options, stdin,
                verbose, args)


    # pylint: disable-msg=C0111
    def fastboot_run(self, command, timeout=3600,
                     ignore_status=False, ignore_timeout=False,
                     stdout=utils.TEE_TO_LOGS, stderr=utils.TEE_TO_LOGS,
                     connect_timeout=30, options='', stdin=None, verbose=True,
                     require_sudo=False, args=()):
        """Runs an fastboot command.

        This command may launch on the adb device or on the adb host.

        Refer to _device_run method for docstring for parameters.
        """
        require_sudo = require_sudo or utils.is_moblab()
        return self._device_run(
                FASTBOOT_CMD, command, False, timeout,
                ignore_status, ignore_timeout, stdout, stderr, connect_timeout,
                options, stdin, verbose, require_sudo, args)


    def _device_run(self, function, command, shell=False,
                    timeout=3600, ignore_status=False, ignore_timeout=False,
                    stdout=utils.TEE_TO_LOGS, stderr=utils.TEE_TO_LOGS,
                    connect_timeout=30, options='', stdin=None, verbose=True,
                    require_sudo=False, args=()):
        """Runs a command named `function`.

        This command may launch on the adb device or on the adb host.

        @param command: Command to run.
        @param shell: If true the command runs in the adb shell otherwise if
                      False it will be passed directly to adb. For example
                      reboot with shell=False will call 'adb reboot'. This
                      option only applies to function adb.
        @param timeout: Time limit in seconds before attempting to
                        kill the running process. The run() function
                        will take a few seconds longer than 'timeout'
                        to complete if it has to kill the process.
        @param ignore_status: Do not raise an exception, no matter
                              what the exit code of the command is.
        @param ignore_timeout: Bool True if command timeouts should be
                               ignored.  Will return None on command timeout.
        @param stdout: Redirect stdout.
        @param stderr: Redirect stderr.
        @param connect_timeout: Connection timeout (in seconds)
        @param options: String with additional ssh command options
        @param stdin: Stdin to pass (a string) to the executed command
        @param require_sudo: True to require sudo to run the command. Default is
                             False.
        @param args: Sequence of strings to pass as arguments to command by
                     quoting them in " and escaping their contents if
                     necessary.

        @returns a CMDResult object.

        """
        if function == ADB_CMD:
            serial = self._adb_serial
        elif function == FASTBOOT_CMD:
            serial = self._fastboot_serial
        else:
            raise NotImplementedError('Mode %s is not supported' % function)

        if function != ADB_CMD and shell:
            raise error.CmdError('shell option is only applicable to `adb`.')

        cmd = '%s%s ' % ('sudo -n ' if require_sudo else '', function)

        if serial:
            cmd += '-s %s ' % serial
        elif self._use_tcpip:
            cmd += '-s %s:5555 ' % self._device_hostname

        if shell:
            cmd += '%s ' % SHELL_CMD
        cmd += command

        if verbose:
            logging.debug('Command: %s', cmd)

        if self._local_adb:
            return utils.run(
                    command=cmd, timeout=timeout, ignore_status=ignore_status,
                    ignore_timeout=ignore_timeout, stdout_tee=stdout,
                    stderr_tee=stderr, stdin=stdin, args=args)
        else:
            return super(ADBHost, self).run(
                    command=cmd, timeout=timeout, ignore_status=ignore_status,
                    ignore_timeout=ignore_timeout, stdout_tee=stdout,
                    options=options, stdin=stdin,
                    connect_timeout=connect_timeout, args=args)


    @label_decorator()
    def get_board(self):
        """Determine the correct board label for the device.

        @returns a string representing this device's board.
        """
        # TODO(kevcheng): with multiple hosts, switch this to return a list.
        board = self.run_output('getprop %s' % BOARD_FILE)
        board_os = self.get_os_type()
        board_num = str(self._num_of_boards.get(board, 0) + 1)
        self._num_of_boards[board] = int(board_num)
        return constants.BOARD_PREFIX + '-'.join([board_os, board, board_num])


    def job_start(self):
        """
        Disable log collection on adb_hosts.

        TODO(sbasi): crbug.com/305427

        """


    def run(self, command, timeout=3600, ignore_status=False,
            ignore_timeout=False, stdout_tee=utils.TEE_TO_LOGS,
            stderr_tee=utils.TEE_TO_LOGS, connect_timeout=30, options='',
            stdin=None, verbose=True, args=()):
        """Run a command on the adb device.

        The command given will be ran directly on the adb device; for example
        'ls' will be ran as: 'abd shell ls'

        @param command: The command line string.
        @param timeout: Time limit in seconds before attempting to
                        kill the running process. The run() function
                        will take a few seconds longer than 'timeout'
                        to complete if it has to kill the process.
        @param ignore_status: Do not raise an exception, no matter
                              what the exit code of the command is.
        @param ignore_timeout: Bool True if command timeouts should be
                               ignored.  Will return None on command timeout.
        @param stdout_tee: Redirect stdout.
        @param stderr_tee: Redirect stderr.
        @param connect_timeout: Connection timeout (in seconds).
        @param options: String with additional ssh command options.
        @param stdin: Stdin to pass (a string) to the executed command
        @param args: Sequence of strings to pass as arguments to command by
                     quoting them in " and escaping their contents if
                     necessary.

        @returns A CMDResult object or None if the call timed out and
                 ignore_timeout is True.

        @raises AutoservRunError: If the command failed.
        @raises AutoservSSHTimeout: Ssh connection has timed out.

        """
        command = ('"%s; echo %s:\$?"' %
                (utils.sh_escape(command), CMD_OUTPUT_PREFIX))
        result = self.adb_run(
                command, shell=True, timeout=timeout,
                ignore_status=ignore_status, ignore_timeout=ignore_timeout,
                stdout=stdout_tee, stderr=stderr_tee,
                connect_timeout=connect_timeout, options=options, stdin=stdin,
                verbose=verbose, args=args)
        if not result:
            # In case of timeouts.
            return None

        parse_output = re.match(CMD_OUTPUT_REGEX, result.stdout)
        if not parse_output and not ignore_status:
            raise error.AutoservRunError(
                    'Failed to parse the exit code for command: %s' %
                    command, result)
        elif parse_output:
            result.stdout = parse_output.group('OUTPUT')
            result.exit_status = int(parse_output.group('EXIT_CODE'))
            if result.exit_status != 0 and not ignore_status:
                raise error.AutoservRunError(command, result)
        return result


    def host_run(self, command, timeout=3600, ignore_status=False,
                 ignore_timeout=False, stdout_tee=utils.TEE_TO_LOGS,
                 stderr_tee=utils.TEE_TO_LOGS, connect_timeout=30, options='',
                 stdin=None, args=()):
        """Run a non-adb command on the ADB host.

        Useful if packages need to be staged prior to use via ADB.

        @param command: The command line string.
        @param timeout: Time limit in seconds before attempting to
                        kill the running process. The run() function
                        will take a few seconds longer than 'timeout'
                        to complete if it has to kill the process.
        @param ignore_status: Do not raise an exception, no matter
                              what the exit code of the command is.
        @param ignore_timeout: Bool True if command timeouts should be
                ignored.  Will return None on command timeout.
        @param stdout_tee: Redirect stdout.
        @param stderr_tee: Redirect stderr.
        @param connect_timeout: Connection timeout (in seconds)
        @param options: String with additional ssh command options
        @param stdin: Stdin to pass (a string) to the executed command
        @param args: Sequence of strings to pass as arguments to command by
                     quoting them in " and escaping their contents if necessary

        @returns A CMDResult object or None if the call timed out and
                 ignore_timeout is True.

        """
        if self._local_adb:
            return utils.run(
                    command=command, timeout=timeout,
                    ignore_status=ignore_status, stdout_tee=stdout_tee,
                    stderr_tee=stderr_tee, stdin=stdin, args=args,
                    ignore_timeout=ignore_timeout)
        return super(ADBHost, self).run(
                command=command, timeout=timeout, ignore_status=ignore_status,
                stdout_tee=stdout_tee, options=options, stdin=stdin,
                connect_timeout=connect_timeout, args=args,
                ignore_timeout=ignore_timeout)


    def wait_up(self, timeout=DEFAULT_WAIT_UP_TIME_SECONDS, command=ADB_CMD):
        """Wait until the remote host is up or the timeout expires.

        Overrides wait_down from AbstractSSHHost.

        @param timeout: Time limit in seconds before returning even if the host
                is not up.
        @param command: The command used to test if a device is up, i.e.,
                accessible by the given command. Default is set to `adb`.

        @returns True if the host was found to be up before the timeout expires,
                 False otherwise.
        """
        @retry.retry(error.TimeoutException, timeout_min=timeout/60.0,
                     delay_sec=1)
        def _wait_up():
            if not self.is_up(command=command):
                raise error.TimeoutException('Device is still down.')
            return True

        try:
            _wait_up()
            logging.debug('Host %s is now up, and can be accessed by %s.',
                          self.hostname, command)
            return True
        except error.TimeoutException:
            logging.debug('Host %s is still down after waiting %d seconds',
                          self.hostname, timeout)
            return False


    def wait_down(self, timeout=DEFAULT_WAIT_DOWN_TIME_SECONDS,
                  warning_timer=None, old_boot_id=None, command=ADB_CMD):
        """Wait till the host goes down, i.e., not accessible by given command.

        Overrides wait_down from AbstractSSHHost.

        @param timeout: Time in seconds to wait for the host to go down.
        @param warning_timer: Time limit in seconds that will generate
                              a warning if the host is not down yet.
                              Currently ignored.
        @param old_boot_id: Not applicable for adb_host.
        @param command: `adb`, test if the device can be accessed by adb
                command, or `fastboot`, test if the device can be accessed by
                fastboot command. Default is set to `adb`.

        @returns True if the device goes down before the timeout, False
                 otherwise.

        """
        @retry.retry(error.TimeoutException, timeout_min=timeout/60.0,
                     delay_sec=1)
        def _wait_down():
            if self.is_up(command=command):
                raise error.TimeoutException('Device is still up.')
            return True

        try:
            _wait_down()
            logging.debug('Host %s is now down', self.hostname)
            return True
        except error.TimeoutException:
            logging.debug('Host %s is still up after waiting %d seconds',
                          self.hostname, timeout)
            return False


    def reboot(self):
        """Reboot the android device connected to this host with adb.

        Reboots the device over ADB.

        @raises AutoservRebootError if reboot failed.

        """
        # Not calling super.reboot() as we want to reboot the ADB device not
        # the host we are running ADB on.
        self.adb_run('reboot', timeout=10, ignore_timeout=True)
        if not self.wait_down():
            raise error.AutoservRebootError(
                    'ADB Device is still up after reboot')
        if not self.wait_up():
            raise error.AutoservRebootError(
                    'ADB Device failed to return from reboot.')
        # Reconnect via TCP/IP.
        self._connect_over_tcpip_as_needed()


    def _get_devices(self, use_adb):
        """Get a list of devices currently attached to this adb host.

        @params use_adb: True to get adb accessible devices. Set to False to
                         get fastboot accessible devices.

        @returns a list of devices attached to this adb host.
        """
        if use_adb:
            result = self.adb_run('devices')
        else:
            result = self.fastboot_run('devices')
        devices = []
        for line in result.stdout.splitlines():
            match = re.search(DEVICE_FINDER_REGEX,
                              line)
            if match:
                serial = match.group('SERIAL')
                if serial == DEVICE_NO_SERIAL_MSG or re.match(r'^\?+$', serial):
                    serial = DEVICE_NO_SERIAL_TAG
                logging.debug('Found Device: %s', serial)
                devices.append(serial)
        return devices


    def adb_devices(self):
        """Get a list of devices currently attached to this adb host and
        accessible by adb command.
        """
        devices = self._get_devices(use_adb=True)
        if self._adb_serial is None and len(devices) > 1:
            raise error.AutoservError(
                    'Not given ADB serial but multiple devices detected')
        return devices


    def fastboot_devices(self):
        """Get a list of devices currently attached to this adb host and
        accessible by fastboot command.
        """
        devices = self._get_devices(use_adb=False)
        if self._fastboot_serial is None and len(devices) > 1:
            raise error.AutoservError(
                    'Not given fastboot serial but multiple devices detected')
        return devices


    def is_up(self, timeout=0, command=ADB_CMD):
        """Determine if the specified adb device is up with expected mode.

        @param timeout: Not currently used.
        @param command: `adb`, the device can be accessed by adb command,
                or `fastboot`, the device can be accessed by fastboot command.
                Default is set to `adb`.

        @returns True if the device is detectable by given command, False
                 otherwise.

        """
        if command == ADB_CMD:
            devices = self.adb_devices()
            serial = self._adb_serial
        elif command == FASTBOOT_CMD:
            devices = self.fastboot_devices()
            serial = self._fastboot_serial
        else:
            raise NotImplementedError('Mode %s is not supported' % command)

        return bool(devices and (not serial or serial in devices))


    def close(self):
        """Close the host object.

        Called as the test ends. Will return the device to USB mode and kill
        the ADB server.

        """
        if self._use_tcpip:
            # Return the device to usb mode.
            self.run('adb usb')
        # TODO(sbasi) Originally, we would kill the server after each test to
        # reduce the opportunity for bad server state to hang around.
        # Unfortunately, there is a period of time after each kill during which
        # the Android device becomes unusable, and if we start the next test
        # too quickly, we'll get an error complaining about no ADB device
        # attached.
        #self.adb_run('kill-server')
        return super(ADBHost, self).close()


    def syslog(self, message, tag='autotest'):
        """Logs a message to syslog on host.

        @param message String message to log into syslog
        @param tag String tag prefix for syslog

        """
        self.adb_run('log -t "%s" "%s"' % (tag, message), shell=True)


    def get_autodir(self):
        """Return the directory to install autotest for client side tests."""
        return '/data/autotest'


    def verify_software(self):
        """Verify working software on an adb_host.

        TODO (crbug.com/532222): Actually implement this method.
        """
        return True


    def verify_job_repo_url(self, tag=''):
        """Make sure job_repo_url of this host is valid.

        TODO (crbug.com/532223): Actually implement this method.

        @param tag: The tag from the server job, in the format
                    <job_id>-<user>/<hostname>, or <hostless> for a server job.
        """
        return


    def _get_adb_host_tmpdir(self):
        """Creates a tmp dir for staging on the adb_host.

        @returns the path of the tmp dir created.

        @raises: AutoservError if there is an error creating the tmp dir.
        """
        try:
            tmp_dir = self.host_run("mktemp -d").stdout.strip()
        except (error.AutoservRunError, error.AutoservSSHTimeout) as e:
            raise error.AutoservError(
                    'Failed to create tmp dir on adb_host: %s' % e)
        return tmp_dir


    def send_file(self, source, dest, delete_dest=False,
                  preserve_symlinks=False):
        """Copy files from the drone to the device.

        @param source: The file/directory on the drone to send to the device.
        @param dest: The destination path on the device to copy to.
        @param delete_dest: A flag set to choose whether or not to delete
                            dest on the device if it exists.
        @param preserve_symlinks: Controls if symlinks on the source will be
                                  copied as such on the destination or
                                  transformed into the referenced
                                  file/directory.
        """
        # If we need to preserve symlinks, let's check if the source is a
        # symlink itself and if so, just create it on the device.
        if preserve_symlinks:
            symlink_target = None
            try:
                symlink_target = os.readlink(source)
            except OSError:
                # Guess it's not a symlink.
                pass

            if symlink_target is not None:
                # Once we create the symlink, let's get out of here.
                self.run('ln -s %s %s' % (symlink_target, dest))
                return

        tmp_dir = ''
        src_path = source
        # Stage the files on the adb_host if we're not running on localhost.
        if not self._local_adb:
            tmp_dir = self._get_adb_host_tmpdir()
            src_path = os.path.join(tmp_dir, os.path.basename(dest))
            # Now copy the file over to the adb_host so you can reference the
            # file in the push command.
            super(ADBHost, self).send_file(source, src_path,
                                           preserve_symlinks=preserve_symlinks)

        if delete_dest:
            self.adb_run('rm -rf %s' % dest, shell=True)

        self.adb_run('push %s %s' % (src_path, dest))

        # If we're not local, cleanup the adb_host.
        if not self._local_adb:
            try:
                self.host_run('rm -rf %s' % tmp_dir)
            except (error.AutoservRunError, error.AutoservSSHTimeout) as e:
                logging.warn('failed to remove dir %s: %s', tmp_dir, e)


    def _get_file_info(self, dest):
        """Get permission and possible symlink info about file on the device.

        These files are on the device so we only have shell commands (via adb)
        to get the info we want.  We'll use 'ls' to get it all.

        @param dest: File to get info about.

        @returns a dict of the file permissions and symlink.
        """
        # Grab file info but leave out the name/group for easier regexing.
        file_info = self.run_output('ls -lgo %s' % dest)
        symlink = None
        perms = 0
        match = re.match(FILE_INFO_REGEX, file_info)
        if match:
            # Check if it's a symlink and grab the linked dest if it is.
            if match.group('TYPE') == 'l':
                symlink_match = re.match(FILE_SYMLINK_REGEX, file_info)
                if symlink_match:
                    symlink = symlink_match.group('SYMLINK')

            # Set the perms.
            for perm, perm_flag in zip(match.group('PERMS'), FILE_PERMS_FLAGS):
                if perm != '-':
                    perms |= perm_flag

        return {'perms': perms,
                'symlink': symlink}


    def get_file(self, source, dest, delete_dest=False, preserve_perm=True,
                 preserve_symlinks=False):
        """Copy files from the device to the drone.

        @param source: The file/directory on the device to copy back to the
                       drone.
        @param dest: The destination path on the drone to copy to.
        @param delete_dest: A flag set to choose whether or not to delete
                            dest on the drone if it exists.
        @param preserve_perm: Tells get_file() to try to preserve the sources
                              permissions on files and dirs.
        @param preserve_symlinks: Try to preserve symlinks instead of
                                  transforming them into files/dirs on copy.
        """
        tmp_dir = ''
        dest_path = dest
        # Stage the files on the adb_host if we're not local.
        if not self._local_adb:
            tmp_dir = self._get_adb_host_tmpdir()
            dest_path = os.path.join(tmp_dir, os.path.basename(source))

        if delete_dest:
            utils.run('rm -rf %s' % dest)

        source_info = {}
        if preserve_symlinks or preserve_perm:
            source_info = self._get_file_info(source)

        # If we want to preserve symlinks, just create it here, otherwise pull
        # the file off the device.
        if preserve_symlinks and source_info['symlink']:
            os.symlink(source_info['symlink'], dest)
        else:
            self._adb_run('pull %s %s' % (source, dest_path))

            # If not local, copy over the file from the adb_host and clean up.
            if not self._local_adb:
                super(ADBHost, self).get_file(dest_path, dest)
                try:
                    self.host_run('rm -rf %s' % tmp_dir)
                except (error.AutoservRunError, error.AutoservSSHTimeout) as e:
                    logging.warn('failed to remove dir %s: %s', tmp_dir, e)

        if preserve_perm:
            os.chmod(dest, source_info['perms'])


    def get_release_version(self):
        """Get the release version from the RELEASE_FILE on the device.

        @returns The release string in the RELEASE_FILE.

        """
        return self.run_output('getprop %s' % RELEASE_FILE)


    def get_tmp_dir(self, parent=''):
        """Return a suitable temporary directory on the host.

        For adb_host we ensure this is a subdirectory of /data/local/tmp

        @param parent: Parent directory of the returned tmp dir.

        @returns a path to the temp directory on the host.
        """
        if not parent.startswith(TMP_DIR):
            parent = os.path.join(TMP_DIR, parent.lstrip(os.path.sep))
        return super(ADBHost, self).get_tmp_dir(parent=parent)


    def get_platform(self):
        """Determine the correct platform label for this host.

        TODO (crbug.com/536250): Figure out what we want to do for adb_host's
                       get_plaftom.

        @returns a string representing this host's platform.
        """
        return 'adb'


    def get_os_type(self):
        if self.run_output('getprop ro.product.brand') == 'Brillo':
            return 'brillo'
        return 'android'


    def _forward(self, reverse, args):
        """Execute a forwarding command.

        @param reverse: Whether this is reverse forwarding (Boolean).
        @param args: List of command arguments.
        """
        cmd = '%s %s' % ('reverse' if reverse else 'forward', ' '.join(args))
        self.adb_run(cmd)


    def add_forwarding(self, src, dst, reverse=False, rebind=True):
        """Forward a port between the ADB host and device.

        Port specifications are any strings accepted as such by ADB, for
        example 'tcp:8080'.

        @param src: Port specification to forward from.
        @param dst: Port specification to forward to.
        @param reverse: Do reverse forwarding from device to host (Boolean).
        @param rebind: Allow rebinding an already bound port (Boolean).
        """
        args = []
        if not rebind:
            args.append('--no-rebind')
        args += [src, dst]
        self._forward(reverse, args)


    def remove_forwarding(self, src=None, reverse=False):
        """Removes forwarding on port.

        @param src: Port specification, or None to remove all forwarding.
        @param reverse: Whether this is reverse forwarding (Boolean).
        """
        args = []
        if src is None:
            args.append('--remove-all')
        else:
            args += ['--remove', src]
        self._forward(reverse, args)


    def rpc_port_forward(self, port, local_port):
        """
        Forwards a port securely through a tunnel process from the server
        to the DUT for RPC server connection.
        Add a 'ADB forward' rule to forward the RPC packets from the AdbHost
        to the DUT.

        @param port: remote port on the DUT.
        @param local_port: local forwarding port.

        @return: the tunnel process.
        """
        self.add_forwarding('tcp:%s' % port, 'tcp:%s' % port)
        return super(ADBHost, self).rpc_port_forward(port, local_port)


    def rpc_port_disconnect(self, tunnel_proc, port):
        """
        Disconnects a previously forwarded port from the server to the DUT for
        RPC server connection.
        Remove the previously added 'ADB forward' rule to forward the RPC
        packets from the AdbHost to the DUT.

        @param tunnel_proc: the original tunnel process returned from
                            |rpc_port_forward|.
        @param port: remote port on the DUT.

        """
        self.remove_forwarding('tcp:%s' % port)
        super(ADBHost, self).rpc_port_disconnect(tunnel_proc, port)


    def ensure_bootloader_mode(self):
        """Ensure the device  is in bootloader mode.

        @raise: error.AutoservError if the device failed to reboot into
                bootloader mode.
        """
        if self.is_up(command=FASTBOOT_CMD):
            return
        self.adb_run('reboot bootloader')
        if not self.wait_up(command=FASTBOOT_CMD):
            raise error.AutoservError(
                    'The device failed to reboot into bootloader mode.')


    def ensure_adb_mode(self):
        """Ensure the device is up and can be accessed by adb command.

        @raise: error.AutoservError if the device failed to reboot into
                adb mode.
        """
        if self.is_up():
            return
        self.fastboot_run('reboot')
        if not self.wait_up():
            raise error.AutoservError(
                    'The device failed to reboot into adb mode.')
