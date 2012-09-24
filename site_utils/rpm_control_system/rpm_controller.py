# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ConfigParser
import logging
import pexpect
import Queue
import re
import threading
import time

from config import rpm_config
import dli_urllib


# Format Appears as: [Date] [Time] - [Msg Level] - [Message]
LOGGING_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
CONFIG_FILE = 'rpm_config.ini'
CONFIG = ConfigParser.ConfigParser()
CONFIG.read(CONFIG_FILE)


class RPMController(object):
    """
    This abstract class implements RPM request queueing and
    processes queued requests.

    The actual interaction with the RPM device will be implemented
    by the RPM specific subclasses.

    It assumes that you know the RPM hostname and that the DUT is on
    the specified RPM.

    This class also allows support for RPM devices that can be accessed
    directly or through a hydra serial concentrator device.

    Implementation details:
    This is an abstract class, subclasses must implement the methods
    listed here. You must not instantiate this class but should
    instantiate one of those leaf subclasses.

    @var behind_hydra: boolean value to represent whether or not this RPM is
                        behind a hydra device.
    @var hostname: hostname for this rpm device.
    @var is_running_lock: lock used to control access to _running.
    @var request_queue: queue used to store requested outlet state changes.
    @var queue_lock: lock used to control access to request_queue.
    @var _running: boolean value to represent if this controller is currently
                   looping over queued requests.
    """


    SSH_LOGIN_CMD = 'ssh -l %s -o StrictHostKeyChecking=no ' \
                    '-o UserKnownHostsFile=/dev/null %s'
    USERNAME_PROMPT = 'Username:'
    HYRDA_RETRY_SLEEP_SECS = 10
    HYDRA_MAX_CONNECT_RETRIES = 3
    LOGOUT_CMD = 'logout'
    CLI_CMD = 'CLI'
    CLI_HELD = 'The administrator \[root\] has an active .* session.'
    CLI_KILL_PREVIOUS = 'cancel'
    CLI_PROMPT = 'cli>'
    HYDRA_PROMPT = '#'
    PORT_STATUS_CMD = 'portStatus'
    QUIT_CMD = 'quit'
    SESSION_KILL_CMD_FORMAT = 'administration sessions kill %s'
    HYDRA_CONN_HELD_MSG_FORMAT = 'is being used'

    # Global Variables that will likely be changed by subclasses.
    DEVICE_PROMPT = '$'
    PASSWORD_PROMPT = 'Password:'
    # The state change command can be any string format but must accept 2 vars:
    # state followed by DUT/Plug name.
    STATE_CMD = '%s %s'
    SUCCESS_MSG = None # Some RPM's may not return a success msg.


    def __init__(self, rpm_hostname, hydra_name=None):
        """
        RPMController Constructor.
        To be called by subclasses.

        @param rpm_hostname: hostname of rpm device to be controlled.
        """
        self._dns_zone = CONFIG.get('CROS', 'dns_zone')
        self.hostname = rpm_hostname
        self.request_queue = Queue.Queue()
        self._running = False
        self.is_running_lock = threading.Lock()
        self.behind_hydra = False
        # If a hydra name is provided by the subclass then we know we are
        # talking to an rpm behind a hydra device.
        if hydra_name:
            self.behind_hydra = True
            self.hydra_name = hydra_name
            self._hydra_hostname = CONFIG.get(hydra_name,'hostname')


    def _start_processing_requests(self):
        """
        Check if there is a thread processing requests.
        If not start one.
        """
        with self.is_running_lock:
            if not self._running:
                self._running = True
                self._running_thread = threading.Thread(target=self._run)
                self._running_thread.start()


    def _stop_processing_requests(self):
        """
        Called if the request request_queue is empty.
        Set running status to false.
        """
        with self.is_running_lock:
            logging.debug('Request queue is empty. RPM Controller for %s'
                          ' is terminating.', self.hostname)
            self._running = False
        if not self.request_queue.empty():
            # This can occur if an item was pushed into the queue after we
            # exited the while-check and before the _stop_processing_requests
            # call was made. Therefore we need to start processing again.
            self._start_processing_requests()


    def _run(self):
        """
        Processes all queued up requests for this RPM Controller.
        Callers should first request_queue up atleast one request and if this
        RPM Controller is not running then call run.

        Caller can either simply call run but then they will be blocked or
        can instantiate a new thread to process all queued up requests.
        For example:
          threading.Thread(target=rpm_controller.run).start()

        Requests are in the format of:
          [dut_hostname, new_state, condition_var, result]
        Run will set the result with the correct value.
        """
        while not self.request_queue.empty():
            request = self.request_queue.get()
            result = self.set_power_state(request['dut'], request['new_state'])
            if not result:
                logging.error('Request to change %s to state %s failed.',
                              request['dut'], request['new_state'])
            # Put result inside the result Queue to allow the caller to resume.
            request['result_queue'].put(result)
        self._stop_processing_requests()


    def queue_request(self, dut_hostname, new_state):
        """
        Queues up a requested state change for a DUT's outlet.

        Requests are in the format of:
          [dut_hostname, new_state, condition_var, result]
        Run will set the result with the correct value.

        @param dut_hostname: hostname of DUT whose outlet we want to change.
        @param new_state: ON/OFF/CYCLE - state or action we want to perform on
                          the outlet.
        """
        request = {}
        request['dut'] = dut_hostname
        request['new_state'] = new_state
        # Reserve a spot for the result to be stored.
        request['result_queue'] = Queue.Queue()
        # Place in request_queue
        self.request_queue.put(request)
        self._start_processing_requests()
        # Block until the request is processed.
        result = request['result_queue'].get(block=True)
        return result


    def _kill_previous_connection(self):
        """
        In case the port to the RPM through the hydra serial concentrator is in
        use, terminate the previous connection so we can log into the RPM.

        It logs into the hydra serial concentrator over ssh, launches the CLI
        command, gets the port number and then kills the current session.
        """
        ssh = self._authenticate_with_hydra(admin_override=True)
        if not ssh:
            return
        ssh.expect(RPMController.PASSWORD_PROMPT, timeout=60)
        ssh.sendline(CONFIG.get(self.hydra_name, 'admin_password'))
        ssh.expect(RPMController.HYDRA_PROMPT)
        ssh.sendline(RPMController.CLI_CMD)
        cli_prompt_re = re.compile(RPMController.CLI_PROMPT)
        cli_held_re = re.compile(RPMController.CLI_HELD)
        response = ssh.expect_list([cli_prompt_re, cli_held_re], timeout=60)
        if response == 1:
            # Need to kill the previous adminstator's session.
            logging.error("Need to disconnect previous administrator's CLI "
                          "session to release the connection to RPM device %s.",
                          self.hostname)
            ssh.sendline(RPMController.CLI_KILL_PREVIOUS)
            ssh.expect(RPMController.CLI_PROMPT)
        ssh.sendline(RPMController.PORT_STATUS_CMD)
        ssh.expect(': %s' % self.hostname)
        ports_status = ssh.before
        port_number = ports_status.split(' ')[-1]
        ssh.expect(RPMController.CLI_PROMPT)
        ssh.sendline(RPMController.SESSION_KILL_CMD_FORMAT % port_number)
        ssh.expect(RPMController.CLI_PROMPT)
        self._logout(ssh, admin_logout=True)


    def _hydra_login(self, ssh):
        """
        Perform the extra steps required to log into a hydra serial
        concentrator.

        @param ssh: pexpect.spawn object used to communicate with the hydra
                    serial concentrator.

        @return: True if the login procedure is successful. False if an error
                 occurred. The most common case would be if another user is
                 logged into the device.
        """
        try:
            response = ssh.expect_list(
                    [re.compile(RPMController.PASSWORD_PROMPT),
                     re.compile(RPMController.HYDRA_CONN_HELD_MSG_FORMAT)],
                    timeout=15)
        except pexpect.TIMEOUT:
            # If there was a timeout, this ssh tunnel could be set up to
            # not require the hydra password.
            ssh.sendline('')
            try:
                ssh.expect(re.compile(RPMController.USERNAME_PROMPT))
                logging.debug('Connected to rpm through hydra. Logging in.')
                return True
            except pexpect.ExceptionPexpect:
                return False
        if response == 0:
            try:
                ssh.sendline(CONFIG.get(self.hydra_name,'password'))
                ssh.sendline('')
                response = ssh.expect_list(
                        [re.compile(RPMController.USERNAME_PROMPT),
                         re.compile(RPMController.HYDRA_CONN_HELD_MSG_FORMAT)],
                        timeout=60)
            except pexpect.EOF:
                # Did not receive any of the expect responses, retry.
                return False
            except pexpect.TIMEOUT:
                logging.debug('Timeout occurred logging in to hydra.')
                return False
        # Send the username that the subclass will have set in its
        # construction.
        if response == 1:
            logging.debug('SSH Terminal most likely serving another'
                          ' connection, retrying.')
            # Kill the connection for the next connection attempt.
            try:
                self._kill_previous_connection()
            except pexpect.ExceptionPexpect:
                logging.error('Failed to disconnect previous connection, '
                              'retrying.')
                raise
            return False
        logging.debug('Connected to rpm through hydra. Logging in.')
        return True


    def _authenticate_with_hydra(self, admin_override=False):
        """
        Some RPM's are behind a hydra serial concentrator and require their ssh
        connection to be tunneled through this device. This can fail if another
        user is logged in; therefore this will retry multiple times.

        This function also allows us to authenticate directly to the
        administrator interface of the hydra device.

        @param admin_override: Set to True if we are trying to access the
                               administrator interface rather than tunnel
                               through to the RPM.

        @return: The connected pexpect.spawn instance if the login procedure is
                 successful. None if an error occurred. The most common case
                 would be if another user is logged into the device.
        """
        if admin_override:
            username = CONFIG.get(self.hydra_name, 'admin_username')
        else:
            username = '%s:%s' % (CONFIG.get(self.hydra_name,'username'),
                                  self.hostname)
        cmd = RPMController.SSH_LOGIN_CMD % (username, self._hydra_hostname)
        num_attempts = 0
        while num_attempts < RPMController.HYDRA_MAX_CONNECT_RETRIES:
            try:
                ssh = pexpect.spawn(cmd)
            except pexpect.ExceptionPexpect:
                return None
            if admin_override:
                return ssh
            if self._hydra_login(ssh):
                return ssh
            # Authenticating with hydra failed. Sleep then retry.
            time.sleep(RPMController.HYRDA_RETRY_SLEEP_SECS)
            num_attempts += 1
        logging.error('Failed to connect to the hydra serial concentrator after'
                      ' %d attempts.', RPMController.HYDRA_MAX_CONNECT_RETRIES)
        return None


    def _login(self):
        """
        Log in into the RPM Device.

        The login process should be able to connect to the device whether or not
        it is behind a hydra serial concentrator.

        @return: ssh - a pexpect.spawn instance if the connection was successful
                 or None if it was not.
        """
        if self.behind_hydra:
            # Tunnel the connection through the hydra.
            ssh = self._authenticate_with_hydra()
            if not ssh:
                return None
            ssh.sendline(self._username)
        else:
            # Connect directly to the RPM over SSH.
            hostname = '%s.%s' % (self.hostname, self._dns_zone)
            cmd = RPMController.SSH_LOGIN_CMD % (self._username, hostname)
            try:
                ssh = pexpect.spawn(cmd)
            except pexpect.ExceptionPexpect:
                return None
        # Wait for the password prompt
        try:
            ssh.expect(self.PASSWORD_PROMPT, timeout=60)
            ssh.sendline(self._password)
            ssh.expect(self.DEVICE_PROMPT, timeout=60)
        except pexpect.ExceptionPexpect:
            return None
        return ssh


    def _logout(self, ssh, admin_logout=False):
        """
        Log out of the RPM device.

        Send the device specific logout command and if the connection is through
        a hydra serial concentrator, kill the ssh connection.

        @param admin_logout: Set to True if we are trying to logout of the
                             administrator interface of a hydra serial
                             concentrator, rather than an RPM.
        @param ssh: pexpect.spawn instance to use to send the logout command.
        """
        if admin_logout:
            ssh.sendline(RPMController.QUIT_CMD)
            ssh.expect(RPMController.HYDRA_PROMPT)
        ssh.sendline(self.LOGOUT_CMD)
        if self.behind_hydra and not admin_logout:
            # Terminate the hydra session.
            ssh.sendline('~.')
            # Wait a bit so hydra disconnects completely. Launching another
            # request immediately can cause a timeout.
            time.sleep(5)


    def set_power_state(self, dut_hostname, new_state):
        """
        Set the state of the dut's outlet on this RPM.

        For ssh based devices, this will create the connection either directly
        or through a hydra tunnel and call the underlying _change_state function
        to be implemented by the subclass device.

        For non-ssh based devices, this method should be overloaded with the
        proper connection and state change code. And the subclass will handle
        accessing the RPM devices.

        @param dut_hostname: hostname of DUT whose outlet we want to change.
        @param new_state: ON/OFF/CYCLE - state or action we want to perform on
                          the outlet.

        @return: True if the attempt to change power state was successful,
                 False otherwise.
        """
        if dut_hostname.startswith('chromeos2'):
            # Because the devices behind in chromeos2 lab all have long
            # hostnames, we can't store their full names in the rpm, therefore
            # for these devices we drop the 'chromeos2' part of their name.
            # For example: chromeos2-rack2-row1-host1 is just stored as
            # rack2-row1-host1 inside the RPM.
            dut_hostname = dut_hostname.split('-', 1)[1]
        ssh = self._login()
        if not ssh:
            return False
        # Try to change the state of the DUT's power outlet.
        result = self._change_state(dut_hostname, new_state, ssh)
        # Terminate hydra connection if necessary.
        self._logout(ssh)
        return result


    def _change_state(self, dut_hostname, new_state, ssh):
        """
        Perform the actual state change operation.

        Once we have established communication with the RPM this method is
        responsible for changing the state of the RPM outlet.

        @param dut_hostname: hostname of DUT whose outlet we want to change.
        @param new_state: ON/OFF/CYCLE - state or action we want to perform on
                          the outlet.
        @param ssh: The ssh connection used to execute the state change commands
                    on the RPM device.

        @return: True if the attempt to change power state was successful,
                 False otherwise.
        """
        ssh.sendline(self.SET_STATE_CMD % (new_state, dut_hostname))
        if self.SUCCESS_MSG:
            # If this RPM device returns a success message check for it before
            # continuing.
            try:
                ssh.expect(self.SUCCESS_MSG, timeout=60)
            except pexpect.ExceptionPexpect:
                logging.error('Request to change outlet for DUT: %s to new '
                              'state %s failed.', dut_hostname, new_state)
                return False
        logging.debug('Outlet for DUT: %s set to %s', dut_hostname, new_state)
        return True


    def type(self):
        """
        Get the type of RPM device we are interacting with.
        To be implemented by the subclasses.

        @return: string representation of RPM device type.
        """
        raise NotImplementedError('Abstract class. Subclasses should implement '
                                  'type().')


class SentryRPMController(RPMController):
    """
    This class implements power control for Sentry Switched CDU
    http://www.servertech.com/products/switched-pdus/

    Example usage:
      rpm = SentrySwitchedCDU('chromeos-rack1-rpm1')
      rpm.queue_request('chromeos-rack1-host1', 'ON')

    @var _username: username used to access device.
    @var _password: password used to access device.
    """


    DEVICE_PROMPT = 'Switched CDU:'
    SET_STATE_CMD = '%s %s'
    SUCCESS_MSG = 'Command successful'


    def __init__(self, hostname, hydra_name=None):
        if hostname.startswith('chromeos2'):
            hydra_name = 'hydra1'
        super(SentryRPMController, self).__init__(hostname, hydra_name)
        self._username = CONFIG.get('SENTRY', 'username')
        self._password = CONFIG.get('SENTRY', 'password')


    def type(self):
        return 'Sentry'


class WebPoweredRPMController(RPMController):
    """
    This class implements RPMController for the Web Powered units
    produced by Digital Loggers Inc.

    @var _rpm: dli_urllib.Powerswitch instance used to interact with RPM.
    """


    CYCLE_SLEEP_TIME = 5


    def __init__(self, hostname, powerswitch=None):
        username = CONFIG.get('WEBPOWERED', 'username')
        password = CONFIG.get('WEBPOWERED', 'password')
        # Call the constructor in RPMController. However since this is a web
        # accessible device, there should not be a need to tunnel through a
        # hydra serial concentrator.
        super(WebPoweredRPMController, self).__init__(hostname)
        self.hostname = '%s.%s' % (self.hostname, self._dns_zone)
        if not powerswitch:
            self._rpm = dli_urllib.Powerswitch(hostname=self.hostname,
                                               userid=username,
                                               password=password)
        else:
            # Should only be used in unit_testing
            self._rpm = powerswitch


    def _get_outlet_value_and_state(self, dut_hostname):
        """
        Look up the outlet and state for a given hostname on the RPM.

        @param dut_hostname: hostname of DUT whose outlet we want to lookup.

        @return [outlet, state]: the outlet number as well as its current state.
        """
        status_list = self._rpm.statuslist()
        for outlet, hostname, state in status_list:
            if hostname == dut_hostname:
                return outlet, state
        return None


    def set_power_state(self, dut_hostname, new_state):
        """
        Since this does not utilize SSH in any manner, this will overload the
        set_power_state in RPMController and completes all steps of changing
        the DUT's outlet state.
        """
        outlet_and_state = self._get_outlet_value_and_state(dut_hostname)
        if not outlet_and_state:
            logging.error('DUT %s is not on rpm %s',
                          dut_hostname, self.hostname)
            return False
        outlet, state = outlet_and_state
        expected_state = new_state
        if new_state == 'CYCLE':
            logging.debug('Beginning Power Cycle for DUT: %s',
                          dut_hostname)
            self._rpm.off(outlet)
            logging.debug('Outlet for DUT: %s set to OFF', dut_hostname)
            # Pause for 5 seconds before restoring power.
            time.sleep(WebPoweredRPMController.CYCLE_SLEEP_TIME)
            self._rpm.on(outlet)
            logging.debug('Outlet for DUT: %s set to ON', dut_hostname)
            expected_state = 'ON'
        if new_state == 'OFF':
            self._rpm.off(outlet)
            logging.debug('Outlet for DUT: %s set to OFF', dut_hostname)
        if new_state == 'ON':
            self._rpm.on(outlet)
            logging.debug('Outlet for DUT: %s set to ON', dut_hostname)
        # Lookup the final state of the outlet
        return self._is_plug_state(dut_hostname, expected_state)


    def _is_plug_state(self, dut_hostname, expected_state):
        outlet, state = self._get_outlet_value_and_state(dut_hostname)
        if expected_state not in state:
            logging.error('Outlet for DUT: %s did not change to new state'
                          ' %s', dut_hostname, expected_state)
            return False
        return True


    def type(self):
        return 'Webpowered'


def test_in_order_requests():
    """Simple integration testing."""
    rpm = WebPoweredRPMController('chromeos-rack8e-rpm1')
    rpm.queue_request('chromeos-rack8e-hostbs1', 'OFF')
    rpm.queue_request('chromeos-rack8e-hostbs2', 'OFF')
    rpm.queue_request('chromeos-rack8e-hostbs3', 'CYCLE')


def test_parrallel_webrequests():
    """Simple integration testing."""
    rpm = WebPoweredRPMController('chromeos-rack8e-rpm1')
    threading.Thread(target=rpm.queue_request,
                     args=('chromeos-rack8e-hostbs1', 'OFF')).start()
    threading.Thread(target=rpm.queue_request,
                     args=('chromeos-rack8e-hostbs2', 'ON')).start()


def test_parrallel_sshrequests():
    """Simple integration testing."""
    rpm = SentryRPMController('chromeos-rack8-rpm1')
    rpm2 = SentryRPMController('chromeos2-row2-rack3-rpm1')
    threading.Thread(target=rpm.queue_request,
                     args=('chromeos-rack8-hostbs1', 'OFF')).start()
    threading.Thread(target=rpm.queue_request,
                     args=('chromeos-rack8-hostbs2', 'OFF')).start()
    threading.Thread(target=rpm2.queue_request,
                     args=('chromeos2-row2-rack3-hostbs', 'ON')).start()
    threading.Thread(target=rpm2.queue_request,
                     args=('chromeos2-row2-rack3-hostbs2', 'ON')).start()
    threading.Thread(target=rpm2.queue_request,
                     args=('chromeos2-row1-rack7-hostbs1', 'ON')).start()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format=LOGGING_FORMAT)
    test_in_order_requests()
    test_parrallel_webrequests()
    test_parrallel_sshrequests()