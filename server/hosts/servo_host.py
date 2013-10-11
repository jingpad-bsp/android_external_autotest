# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Expects to be run in an environment with sudo and no interactive password
# prompt, such as within the Chromium OS development chroot.


"""This file provides core logic for servo verify/repair process."""


import httplib
import logging
import socket
import time
import xmlrpclib

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import retry
from autotest_lib.server.cros.servo import servo
from autotest_lib.server.hosts import ssh_host
from autotest_lib.site_utils.graphite import stats
from autotest_lib.site_utils.rpm_control_system import rpm_client


class ServoHostException(error.AutoservError):
    """This is the base class for exceptions raised by ServoHost."""
    pass


class ServoHostVerifyFailure(ServoHostException):
    """Raised when servo verification fails."""
    pass


class ServoHostRepairFailure(ServoHostException):
    """Raised when a repair method fails to repair a servo host."""
    pass


class ServoHostRepairMethodNA(ServoHostException):
    """Raised when a repair method is not applicable."""
    pass


class ServoHostRepairTotalFailure(ServoHostException):
    """Raised if all attempts to repair a servo host fail."""
    pass


def make_servo_hostname(dut_hostname):
    """Given a DUT's hostname, return the hostname of its servo.

    @param dut_hostname: hostname of a DUT.

    @return hostname of the DUT's servo.

    """
    host_parts = dut_hostname.split('.')
    host_parts[0] = host_parts[0] + '-servo'
    return '.'.join(host_parts)


class ServoHost(ssh_host.SSHHost):
    """Host class for a host that controls a servo, e.g. beaglebone."""

    # Timeout for getting the value of 'pwr_button'.
    PWR_BUTTON_CMD_TIMEOUT_SECS = 15
    # Timeout for rebooting servo host.
    REBOOT_TIMEOUT_SECS = 90
    HOST_DOWN_TIMEOUT_SECS = 60
    # Delay after rebooting for servod to become fully functional.
    REBOOT_DELAY_SECS = 20
    # Servod process name.
    SERVOD_PROCESS = 'servod'

    _MAX_POWER_CYCLE_ATTEMPTS = 3


    def _initialize(self, servo_host='localhost', servo_port=9999,
                    *args, **dargs):
        """Initialize a ServoHost instance.

        A ServoHost instance represents a host that controls a servo.

        @param servo_host: Name of the host where the servod process
                           is running.
        @param servo_port: Port the servod process is listening on.

        """
        super(ServoHost, self)._initialize(hostname=servo_host,
                                           *args, **dargs)
        self._is_in_lab = utils.host_is_in_lab_zone(self.hostname)
        self._is_localhost = (self.hostname == 'localhost')
        remote = 'http://%s:%s' % (self.hostname, servo_port)
        self._servod_server = xmlrpclib.ServerProxy(remote)
        # Commands on the servo host must be run by the superuser. Our account
        # on Beaglebone is root, but locally we might be running as a
        # different user. If so - `sudo ' will have to be added to the
        # commands.
        if self._is_localhost:
            self._sudo_required = utils.system_output('id -u') != '0'
        else:
            self._sudo_required = False


    def is_in_lab(self):
        """Check whether the servo host is a lab device.

        @returns: True if the servo host is in Cros Lab, otherwise False.

        """
        return self._is_in_lab


    def is_localhost(self):
        """Checks whether the servo host points to localhost.

        @returns: True if it points to localhost, otherwise False.

        """
        return self._is_localhost


    def get_servod_server_proxy(self):
        """Return a proxy that can be used to communicate with servod server.

        @returns: An xmlrpclib.ServerProxy that is connected to the servod
                  server on the host.

        """
        return self._servod_server


    def get_wait_up_processes(self):
        """Get the list of local processes to wait for in wait_up.

        Override get_wait_up_processes in
        autotest_lib.client.common_lib.hosts.base_classes.Host.
        Wait for servod process to go up. Called by base class when
        rebooting the device.

        """
        processes = [self.SERVOD_PROCESS]
        return processes


    def make_ssh_command(self, user='root', port=22, opts='', hosts_file=None,
                         connect_timeout=None, alive_interval=None):
        """Override default make_ssh_command to use tuned options.

        Tuning changes:
          - ConnectTimeout=30; maximum of 30 seconds allowed for an SSH
          connection failure. Consistency with remote_access.py.

          - ServerAliveInterval=180; which causes SSH to ping connection every
          180 seconds. In conjunction with ServerAliveCountMax ensures
          that if the connection dies, Autotest will bail out quickly.

          - ServerAliveCountMax=3; consistency with remote_access.py.

          - ConnectAttempts=4; reduce flakiness in connection errors;
          consistency with remote_access.py.

          - UserKnownHostsFile=/dev/null; we don't care about the keys.

          - SSH protocol forced to 2; needed for ServerAliveInterval.

        @param user User name to use for the ssh connection.
        @param port Port on the target host to use for ssh connection.
        @param opts Additional options to the ssh command.
        @param hosts_file Ignored.
        @param connect_timeout Ignored.
        @param alive_interval Ignored.

        @returns: An ssh command with the requested settings.

        """
        base_command = ('/usr/bin/ssh -a -x %s -o StrictHostKeyChecking=no'
                        ' -o UserKnownHostsFile=/dev/null -o BatchMode=yes'
                        ' -o ConnectTimeout=30 -o ServerAliveInterval=180'
                        ' -o ServerAliveCountMax=3 -o ConnectionAttempts=4'
                        ' -o Protocol=2 -l %s -p %d')
        return base_command % (opts, user, port)


    def _make_scp_cmd(self, sources, dest):
        """Format scp command.

        Given a list of source paths and a destination path, produces the
        appropriate scp command for encoding it. Remote paths must be
        pre-encoded. Overrides _make_scp_cmd in AbstractSSHHost
        to allow additional ssh options.

        @param sources: A list of source paths to copy from.
        @param dest: Destination path to copy to.

        @returns: An scp command that copies |sources| on local machine to
                  |dest| on the remote servo host.

        """
        command = ('scp -rq %s -o BatchMode=yes -o StrictHostKeyChecking=no '
                   '-o UserKnownHostsFile=/dev/null -P %d %s "%s"')
        return command % (self.master_ssh_option,
                          self.port, ' '.join(sources), dest)


    def run(self, command, timeout=3600, ignore_status=False,
            stdout_tee=utils.TEE_TO_LOGS, stderr_tee=utils.TEE_TO_LOGS,
            connect_timeout=30, options='', stdin=None, verbose=True, args=()):
        """Run a command on the servo host.

        Extends method `run` in SSHHost. If the servo host is a remote device,
        it will call `run` in SSHost without changing anything.
        If the servo host is 'localhost', it will call utils.system_output.

        @param command: The command line string.
        @param timeout: Time limit in seconds before attempting to
                        kill the running process. The run() function
                        will take a few seconds longer than 'timeout'
                        to complete if it has to kill the process.
        @param ignore_status: Do not raise an exception, no matter
                              what the exit code of the command is.
        @param stdout_tee/stderr_tee: Where to tee the stdout/stderr.
        @param connect_timeout: SSH connection timeout (in seconds)
                                Ignored if host is 'localhost'.
        @param options: String with additional ssh command options
                        Ignored if host is 'localhost'.
        @param stdin: Stdin to pass (a string) to the executed command.
        @param verbose: Log the commands.
        @param args: Sequence of strings to pass as arguments to command by
                     quoting them in " and escaping their contents if necessary.

        @returns: A utils.CmdResult object.

        @raises AutoservRunError if the command failed.
        @raises AutoservSSHTimeout SSH connection has timed out. Only applies
                when servo host is not 'localhost'.

        """
        run_args = {'command': command, 'timeout': timeout,
                    'ignore_status': ignore_status, 'stdout_tee': stdout_tee,
                    'stderr_tee': stderr_tee, 'stdin': stdin,
                    'verbose': verbose, 'args': args}
        if self.is_localhost():
            if self._sudo_required:
                run_args['command'] = 'sudo -n %s' % command
            try:
                return utils.run(**run_args)
            except error.CmdError as e:
                logging.error(e)
                raise error.AutoservRunError('command execution error',
                                             e.result_obj)
        else:
            run_args['connect_timeout'] = connect_timeout
            run_args['options'] = options
            return super(ServoHost, self).run(**run_args)


    def _check_servod(self):
        """A sanity check of the servod state."""
        msg_prefix = 'Servod error: %s'
        error_msg = None
        try:
            timeout, _ = retry.timeout(
                    self._servod_server.get, args=('pwr_button', ),
                    timeout_sec=self.PWR_BUTTON_CMD_TIMEOUT_SECS)
            if timeout:
                error_msg = msg_prefix % 'Request timed out.'
        except (socket.error, xmlrpclib.Error, httplib.BadStatusLine) as e:
            error_msg = msg_prefix % e
        if error_msg:
            raise ServoHostVerifyFailure(error_msg)


    def _check_servo_host_usb(self):
        """A sanity check of the USB device.

        Sometimes the usb gets wedged due to a kernel bug on the beaglebone.
        A symptom is the presence of /dev/sda without /dev/sda1. The check
        here ensures that if /dev/sda exists, /dev/sda1 must also exist.
        See crbug.com/225932.

        @raises ServoHostVerifyFailure if /dev/sda exists without /dev/sda1 on
            the beaglebone.

        """
        try:
            # The following test exits with a non-zero code
            # and raises AutoserverRunError if error is detected.
            self.run('test ! -b /dev/sda -o -b /dev/sda1')
        except (error.AutoservRunError, error.AutoservSSHTimeout) as e:
            raise ServoHostVerifyFailure(
                    'USB sanity check on %s failed: %s' % (self.hostname, e))


    def verify_software(self):
        """Verify that the servo is in a good state.

        It overrides the base class function for verify_software.
        It checks:
            1) Whether basic servo command can run successfully.
            2) Whether USB is in a good state. crbug.com/225932

        @raises ServoHostVerifyFailure if servo host does not pass the checks.

        """
        logging.info('Verifying servo host %s with sanity checks.',
                     self.hostname)
        self._check_servod()
        self._check_servo_host_usb()
        logging.info('Sanity checks pass on servo host %s', self.hostname)


    def _repair_with_sysrq_reboot(self):
        """Reboot with magic SysRq key."""
        self.reboot(timeout=self.REBOOT_TIMEOUT_SECS,
                    down_timeout=self.HOST_DOWN_TIMEOUT_SECS,
                    reboot_cmd='echo "b" > /proc/sysrq-trigger &',
                    fastsync=True)
        time.sleep(self.REBOOT_DELAY_SECS)


    def has_power(self):
        """Return whether or not the servo host is powered by PoE."""
        # TODO(fdeng): See crbug.com/302791
        # For now, assume all servo hosts in the lab have power.
        return self.is_in_lab()


    def power_cycle(self):
        """Cycle power to this host via PoE if it is a lab device.

        @raises ServoHostRepairFailure if it fails to power cycle the
                servo host.

        """
        if self.has_power():
            try:
                rpm_client.set_power(self.hostname, 'CYCLE')
            except (socket.error, xmlrpclib.Error,
                    httplib.BadStatusLine,
                    rpm_client.RemotePowerException) as e:
                raise ServoHostRepairFailure(
                        'Power cycling %s failed: %s' % (self.hostname, e))
        else:
            logging.info('Skipping power cycling, not a lab device.')


    def _powercycle_to_repair(self):
        """Power cycle the servo host using PoE.

        @raises ServoHostRepairFailure if it fails to fix the servo host.
        @raises ServoHostRepairMethodNA if it does not support power.

        """
        if not self.has_power():
            raise ServoHostRepairMethodNA('%s does not support power.' %
                                          self.hostname)
        logging.info('Attempting repair via PoE powercycle.')
        failed_cycles = 0
        self.power_cycle()
        while not self.wait_up(timeout=self.REBOOT_TIMEOUT_SECS):
            failed_cycles += 1
            if failed_cycles >= self._MAX_POWER_CYCLE_ATTEMPTS:
                raise ServoHostRepairFailure(
                        'Powercycled host %s %d times; device did not come back'
                        ' online.' % (self.hostname, failed_cycles))
            self.power_cycle()
        logging.info('Powercycling was successful after %d failures.',
                     failed_cycles)
        # Allow some time for servod to get started.
        time.sleep(self.REBOOT_DELAY_SECS)


    def repair_full(self):
        """Attempt to repair servo host.

        This overrides the base class function for repair.
        Note if the host is not in Cros Lab, the repair procedure
        will be skipped.

        @raises ServoHostRepairTotalFailure if all attempts fail.

        """
        if not self.is_in_lab():
            logging.warn('Skip repairing servo host %s: Not a lab device.',
                         self.hostname)
            return
        logging.info('Attempting to repair servo host %s.', self.hostname)
        repair_funcs = [self._repair_with_sysrq_reboot,
                        self._powercycle_to_repair]
        errors = []
        for repair_func in repair_funcs:
            counter_prefix = 'servo_host_repair.%s.' % repair_func.__name__
            try:
                repair_func()
                self.verify()
                stats.Counter(counter_prefix + 'SUCCEEDED').increment()
                return
            except ServoHostRepairMethodNA as e:
                logging.warn('Repair method NA: %s', e)
                stats.Counter(counter_prefix + 'RepairNA').increment()
                errors.append(str(e))
            except Exception as e:
                logging.warn('Failed to repair servo: %s', e)
                stats.Counter(counter_prefix + 'FAILED').increment()
                errors.append(str(e))
        stats.Counter('servo_host_repair.Full_Repair_Failed').increment()
        raise ServoHostRepairTotalFailure(
                'All attempts at repairing the servo failed:\n%s' %
                '\n'.join(errors))


    def create_healthy_servo_object(self):
        """Create a servo.Servo object.

        Create a servo.Servo object. If the servo host is in Cros Lab,
        this method will first verify the servo host and attempt to repair it if
        error is detected.

        @raises ServoHostRepairTotalFailure if it fails to fix the servo host.
        @raises AutoservSshPermissionDeniedError if the DUT is not ssh-able
                due to permission error.

        """
        if self.is_in_lab():
            try:
                self.verify()
            except (error.AutoservSSHTimeout,
                    error.AutoservSshPingHostError,
                    error.AutoservHostIsShuttingDownError,
                    ServoHostVerifyFailure):
                self.repair_full()
            except error.AutoservSshPermissionDeniedError:
                raise
        return servo.Servo(servo_host=self)
