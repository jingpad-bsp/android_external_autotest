# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ConfigParser
import logging
import pexpect
import Queue
import threading
import time

import dli


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

    Implementation details:
    This is an abstract class, subclasses must implement the methods
    listed here. You must not instantiate this class but should
    instantiate one of those leaf subclasses.

    @var hostname: hostname for this rpm device.
    @var is_running_lock: lock used to control access to _running.
    @var request_queue: queue used to store requested outlet state changes.
    @var queue_lock: lock used to control access to request_queue.
    @var _running: boolean value to represent if this controller is currently
                   looping over queued requests.
    """


    def __init__(self, rpm_hostname):
        """
        RPMController Constructor.
        To be called by subclasses.

        @param rpm_hostname: hostname of rpm device to be controlled.
        """
        dns_zone = CONFIG.get('CROS', 'dns_zone')
        self.hostname = '.'.join([rpm_hostname, dns_zone])
        self.request_queue = Queue.Queue()
        self._running = False
        self.is_running_lock = threading.Lock()


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


    def set_power_state(self, dut_hostname, new_state):
        """
        Set the state of the dut's outlet on this RPM.
        To be implemented by the subclasses.

        @param dut_hostname: hostname of DUT whose outlet we want to change.
        @param new_state: ON/OFF/CYCLE - state or action we want to perform on
                          the outlet.

        @return: True if the attempt to change power state was successful,
                 False otherwise.
        """
        raise NotImplementedError('Abstract class. Subclasses should implement '
                                  'set_power_state().')


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
    @var _ssh_mock: mocked ssh interface used for testing.
    """


    DEVICE_PROMPT = 'Switched CDU:'
    SSH_LOGIN_CMD = 'ssh -l %s -o StrictHostKeyChecking=no ' \
                    '-o UserKnownHostsFile=/dev/null %s'
    PASSWORD_PROMPT = 'Password:'
    SET_STATE_CMD = '%s %s'
    SUCCESS_MSG = 'Command successful'
    LOGOUT_CMD = 'logout'


    def __init__(self, hostname, ssh_mock=None):
        super(SentryRPMController, self).__init__(hostname)
        self._username = CONFIG.get('SENTRY', 'username')
        self._password = CONFIG.get('SENTRY', 'password')
        self._ssh_mock = ssh_mock


    def set_power_state(self, dut_hostname, new_state):
        logging.debug("Setting outlet for DUT: %s to state: %s",
                      dut_hostname, new_state)
        result = True
        cmd = SentryRPMController.SSH_LOGIN_CMD % (self._username,
                                                   self.hostname)
        if not self._ssh_mock: # For testing purposes.
            ssh = pexpect.spawn(cmd)
        else:
            ssh = self._ssh_mock
        ssh.expect(SentryRPMController.PASSWORD_PROMPT, timeout=60)
        ssh.sendline(self._password)
        ssh.expect(SentryRPMController.DEVICE_PROMPT, timeout=60)
        ssh.sendline(SentryRPMController.SET_STATE_CMD % (new_state,
                                                          dut_hostname))
        try:
            ssh.expect(SentryRPMController.SUCCESS_MSG, timeout=60)
        except pexpect.TIMEOUT:
            logging.error('Request to change outlet for DUT: %s to new '
                          'state %s timed out.', dut_hostname, new_state)
            result = False
        finally:
            ssh.sendline(SentryRPMController.LOGOUT_CMD)
        return result


    def type(self):
        return 'Sentry'


class WebPoweredRPMController(RPMController):
    """
    This class implements RPMController for the Web Powered units
    produced by Digital Loggers Inc.

    @var _rpm: dli.powerswitch instance used to interact with RPM.
    """


    CYCLE_SLEEP_TIME = 5


    def __init__(self, hostname, powerswitch=None):
        username = CONFIG.get('WEBPOWERED', 'username')
        password = CONFIG.get('WEBPOWERED', 'password')
        super(WebPoweredRPMController, self).__init__(hostname)
        if not powerswitch:
            self._rpm = dli.powerswitch(hostname=self.hostname, userid=username,
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
                     args=('chromeos-rack8e-hostbs1', 'ON')).start()
    threading.Thread(target=rpm.queue_request,
                     args=('chromeos-rack8e-hostbs2', 'ON')).start()


def test_parrallel_sshrequests():
    """Simple integration testing."""
    rpm = SentryRPMController('chromeos-rack1-rpm1')
    threading.Thread(target=rpm.queue_request,
                     args=('chromeos-rack1-hostbs1', 'OFF')).start()
    threading.Thread(target=rpm.queue_request,
                     args=('chromeos-rack1-hostbs2', 'ON')).start()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format=LOGGING_FORMAT)
    test_in_order_requests()
    test_parrallel_webrequests()
    test_parrallel_sshrequests()

