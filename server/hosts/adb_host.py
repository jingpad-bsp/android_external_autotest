# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import re
import time

import common

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import retry
from autotest_lib.server import utils
from autotest_lib.server.hosts import abstract_ssh


SHELL_CMD = 'shell'
# Regex to find an adb device. Examples:
# 0146B5580B01801B    device
# 018e0ecb20c97a62    device
# 172.22.75.141:5555  device
DEVICE_FINDER_REGEX = ('^(?P<SERIAL>([\w]+)|(\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}))'
                       '([:]5555)?[ \t]+device')
CMD_OUTPUT_PREFIX = 'ADB_CMD_OUTPUT'
CMD_OUTPUT_REGEX = ('(?P<OUTPUT>[\s\S]*)%s:(?P<EXIT_CODE>\d{1,3})' %
                    CMD_OUTPUT_PREFIX)


class ADBHost(abstract_ssh.AbstractSSHHost):
    """This class represents a host running an ADB server."""


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
            result = host.run('which adb 2> /dev/null', timeout=timeout)
        except (error.AutoservRunError, error.AutoservSSHTimeout):
            return False
        return result.exit_status == 0


    def _initialize(self, hostname='localhost', serial=None,
                    device_hostname=None, *args, **dargs):
        """Initialize an ADB Host.

        This will create an ADB Host. Hostname should always refer to the
        host machine connected to an android device. This will either be the
        only android device connected or if there are multiple, serial must be
        specified. If device_hostname is supplied then all ADB commands will
        run over TCP/IP.

        @param hostname: Hostname of the machine running ADB.
        @param serial: Serial number of the android device we want to interact
                       with.
        @param device_hostname: Hostname or IP of the android device we want to
                                interact with. If supplied all ADB interactions
                                run over TCP/IP.

        """
        super(ADBHost, self)._initialize(hostname=hostname, *args, **dargs)
        logging.debug('Initializing ADB Host running on host: %s.', hostname)
        logging.debug('Android Device: Serial:%s, Hostname: %s',
                      serial, device_hostname)
        self._device_hostname = device_hostname
        self._use_tcpip = False
        self._local_adb = False
        if hostname == 'localhost':
            self._local_adb = True

        self._serial = serial
        if not self._serial:
            logging.debug('Serial not provided determining...')
            # Ensure only one device is attached to this host.
            devices = self.adb_devices()
            if not devices:
                raise error.AutoservError('No ADB devices attached.')
            if len(devices) > 1:
                raise error.AutoservError('Multiple ADB devices attached.')
            self._serial = devices[0]
            logging.debug('Using serial: %s', self._serial)

        if self._device_hostname:
            logging.debug('Device Hostname provided. Connecting over TCP/IP')
            self._connect_over_tcpip()
            self._use_tcpip = True


    def _connect_over_tcpip(self,):
        """Connect to the ADB device over tcpip

        @param device_hostname: Device hostname or IP for which we want to
                                connect to. If none, will use
                                self._device_hostname

        """
        if self._device_hostname in self.adb_devices():
            # We previously had a connection to this device, restart the ADB
            # server.
            self._adb_run('kill-server')
        # Ensure that connection commands don't run over TCP/IP.
        self._use_tcpip = False
        self._adb_run('tcpip 5555', use_serial=True, timeout=10,
                      ignore_timeout=True)
        time.sleep(2)
        try:
            self._adb_run('connect %s' % self._device_hostname, use_serial=True)
        except (error.AutoservRunError, error.CmdError) as e:
            raise error.AutoservError('Failed to connect via TCP/IP: %s' % e)
        # Allow ADB a bit of time after connecting before interacting with the
        # device.
        time.sleep(5)
        # Switch back to using TCP/IP.
        self._use_tcpip = True


    def _adb_run(self, command, shell=False, use_serial=False, timeout=3600,
                 ignore_status=False, ignore_timeout=False,
                 stdout=utils.TEE_TO_LOGS, stderr=utils.TEE_TO_LOGS,
                 connect_timeout=30, options='', stdin=None, args=()):
        """Runs an adb command.

        This command may launch on the adb device or on the adb host.

        @param command: Command to run.
        @param shell: If true the command runs in the adb shell otherwise if
                      False it will be passed directly to adb. For example
                      reboot with shell=False will call 'adb reboot'.
        @param use_serial: Use the adb device serial to specify the device
                           the command will run on.
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
        @param args: Sequence of strings to pass as arguments to command by
                     quoting them in " and escaping their contents if
                     necessary.

        @returns a CMDResult object.

        """
        cmd = 'adb '
        if self._use_tcpip and not use_serial:
            cmd += '-s %s:5555 ' % self._device_hostname
        elif self._serial:
            cmd += '-s %s ' % self._serial
        if shell:
            cmd += '%s ' % SHELL_CMD
        cmd += command

        for arg in args:
            cmd += '%s ' % utils.sh_escape(arg)
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


    def get_board(self):
        return 'adb'


    def job_start(self):
        """
        Disable log collection on adb_hosts.

        TODO(sbasi): crbug.com/305427

        """


    def run(self, command, timeout=3600, ignore_status=False,
            ignore_timeout=False, stdout_tee=utils.TEE_TO_LOGS,
            stderr_tee=utils.TEE_TO_LOGS, connect_timeout=30, options='',
            stdin=None, args=()):
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
        command = '"%s; echo %s:\$?"' % (command, CMD_OUTPUT_PREFIX)
        result = self._adb_run(
                command, shell=True, use_serial=False, timeout=timeout,
                ignore_status=ignore_status, ignore_timeout=ignore_timeout,
                stdout=stdout_tee, stderr=stderr_tee,
                connect_timeout=connect_timeout, options=options, stdin=stdin,
                args=args)
        if not result:
            # In case of timeouts.
            return None

        parse_output = re.match(CMD_OUTPUT_REGEX, result.stdout)
        if not parse_output:
            raise error.AutoservRunError(
                    'Failed to parse the exit code for command: %s' % command,
                    result)
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


    def reboot(self):
        """Reboot the android device connected to this host.

        Reboots the device over ADB.

        @returns True if the device comes back before wait_timeout is up.
                 False otherwise.

        """
        # Not calling super.reboot() as we want to reboot the ADB device not
        # the host we are running ADB on.
        self._adb_run('reboot', timeout=10, ignore_timeout=True)
        if not self.wait_down(timeout=10):
            logging.error('ADB Device is still up after reboot')
            return False
        if not self.wait_up(timeout=30):
            logging.error('ADB Device failed to return from reboot.')
            return False
        if self._use_tcpip:
            # Reconnect via TCP/IP.
            self._connect_over_tcpip()
        return True


    def wait_down(self, timeout=None, warning_timer=None, old_boot_id=None):
        """Wait till the host goes down.

        Overrides wait_down from AbstractSSHHost.

        @param timeout: Time in seconds to wait for the host to go down.
        @param warning_timer: Time limit in seconds that will generate
                              a warning if the host is not down yet.
                              Currently ignored.
        @param old_boot_id: Not applicable for adb_host

        @returns True if the device goes down before the timeout, False
                 otherwise.

        """
        @retry.retry(error.TimeoutException, timeout_min=timeout/60.0,
                     delay_sec=1)
        def _wait_down():
            if self.is_up():
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


    def adb_devices(self):
        """Get a list of devices currently attached to this adb host."""
        result = self._adb_run('devices', use_serial=True)
        devices = []
        for line in result.stdout.splitlines():
            match = re.search(DEVICE_FINDER_REGEX,
                              line)
            if match:
                logging.debug('Found Device: %s', match.group('SERIAL'))
                devices.append(match.group('SERIAL'))
        return devices


    def is_up(self, timeout=0):
        """Determine if the specified adb device is up.

        @param timeout: Not currently used.

        @returns True if the device is detectable but ADB, False otherwise.

        """
        return self._serial in self.adb_devices()


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
        #self._adb_run('kill-server')
        return super(ADBHost, self).close()
