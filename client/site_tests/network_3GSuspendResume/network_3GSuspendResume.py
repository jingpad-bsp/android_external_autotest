# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time
import dbus

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import rtc, sys_power

# Special import to define the location of the flimflam library.
from autotest_lib.client.cros import flimflam_test_path
import flimflam


class network_3GSuspendResume(test.test):
    version = 1

    okerrors = [
        # Setting of device power can sometimes result with InProgress error
        # if it is in the process of already doing so.
        'org.chromium.flimflam.Error.InProgress',
    ]

    scenarios = [
        'scenario_suspend_3g_enabled',
        'scenario_suspend_3g_disabled',
        'scenario_suspend_3g_disabled_twice'
    ]

    # This function returns True when cellular service is available.  Otherwise,
    # if the timeout period has been hit, it returns false.
    def cellular_service_available(self, timeout=60):
        flim = flimflam.FlimFlam(dbus.SystemBus())
        service = flim.FindCellularService(timeout)
        if service:
            logging.info('Cellular service is available')
            return True
        logging.info('Cellular service is not available')
        return False

    def get_powered(self, device):
        properties = device.GetProperties()
        logging.debug(properties)
        logging.info('Power state of cellular device is %s ',
                     ['off', 'on'][properties['Powered']])
        return properties['Powered']

    def set_powered(self, device, state):
        try:
            device.SetProperty('Powered', dbus.Boolean(state))
        except dbus.exceptions.DBusException, e:
            if e._dbus_error_name not in network_3GSuspendResume.okerrors:
                raise e
        return self.get_powered(device) == state

    def suspend_resume(self, duration=10):
        alarm_time = rtc.get_seconds() + duration
        logging.info('Suspending machine for: %d\n' % duration)
        rtc.set_wake_alarm(alarm_time)
        sys_power.suspend_to_ram()

    # __get_cellular_device is a hack wrapper around the FindCellularDevice
    # that verifies that GetProperties can be called before proceeding.
    # There appears to be an issue after suspend/resume where GetProperties
    # returns with UnknownMethod called until some time later.
    def __get_cellular_device(self, timeout=30):
        start_time = time.time()
        flim = flimflam.FlimFlam(dbus.SystemBus())
        device = flim.FindCellularDevice(timeout)

        properties = None
        timeout = start_time + timeout
        while properties is None and time.time() < timeout:
            try:
                properties = device.GetProperties()
            except:
                properties = None

            time.sleep(1)

        return device

    # The suspend_3g_enabled test suspends, then resumes the machine while
    # 3g is enabled.
    def scenario_suspend_3g_enabled(self):
        device = self.__get_cellular_device()
        self.set_powered(device, 1)
        if not self.cellular_service_available():
            raise error.TestError('Unable to find cellular service')
        self.suspend_resume(20)

    # The suspend_3g_disabled test suspends, then resumes the machine while
    # 3g is disabled.
    def scenario_suspend_3g_disabled(self):
        device = self.__get_cellular_device()
        self.set_powered(device, 0)
        self.suspend_resume(20)

        # This verifies that the device is in the same state before and after
        # the device is suspended/resumed.
        device = self.__get_cellular_device()
        if self.get_powered(device) != 0:
            raise error.TestError('Device is not in same state it was prior'
                                  'to Suspend/Resume')

        # Turn on the device to make sure we can bring it back up.
        self.set_powered(device, 1)

    # The suspend_3g_disabled_twice subroutine is here because
    # of bug 9405.  The test will suspend/resume the device twice
    # while 3g is disabled.  We will then verify that 3g can be enabled
    # thereafter.
    def scenario_suspend_3g_disabled_twice(self):
        device = self.__get_cellular_device()
        self.set_powered(device, 0)

        for _ in [0, 1]:
            self.suspend_resume(20)

            # This verifies that the device is in the same state before
            # and after the device is suspended/resumed.
            device = self.__get_cellular_device()
            if self.get_powered(device) != 0:
                raise error.TestError('Device is not in same state it was prior'
                                      'to Suspend/Resume')

        # Turn on the device to make sure we can bring it back up.
        self.set_powered(device, 1)

    # This is the wrapper around the running of each scenario with
    # initialization steps and final checks.
    def run_scenario(self, function_name):
        device = self.__get_cellular_device()

        # Initialize all tests with the power off.
        self.set_powered(device, 0)

        function = getattr(self, function_name)
        logging.info('Running scenario %s' % function_name)
        function()

        # By the end of each test, the cellular device should be up.
        # Here we verify that the power state of the device is up, and
        # that the cellular service can be found.
        device = self.__get_cellular_device()

        if not self.get_powered(device) == 1:
            raise error.TestFail('Failed to execute scenario '
                                 '%s' % function_name)
        if not self.cellular_service_available():
            raise error.TestFail('Cellular service is not available at end '
                                 'of %s' % function_name)

    def run_once(self):
        for t in network_3GSuspendResume.scenarios:
            self.run_scenario(t)
