# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Server side bluetooth tests on adapter standalone working states."""

import functools
import logging
import time

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.server import test
from autotest_lib.server.cros.multimedia import remote_facade_factory


def _TestLog(func):
    """A decorator that logs the test reuslts and collects error messages."""
    @functools.wraps(func)
    def wrapper(instance, *args, **kwargs):
        """A wrapper of the decorated method."""
        instance.results = None
        test_result = func(instance, *args, **kwargs)
        if test_result:
            logging.info('passed: %s', func.__name__)
        else:
            fail_msg = 'failed: %s (%s)' % (func.__name__,
                                            str(instance.results))
            logging.error(fail_msg)
            instance.fails.append(fail_msg)
        return test_result
    return wrapper


class bluetooth_AdapterStandalone(test.test):
    """Server side bluetooth adapter standalone tests.

    This test tries to thoroughly verify most of the important work
    states of a standalone bluetooth adapter prior to connecting to
    other bluetooth peripherals.

    In particular, the following subtests are performed. Look at the
    docstrings of the subtests for more details.
    - test_start_bluetoothd
    - test_stop_bluetoothd
    - test_adapter_work_state
    - test_power_on_adapter
    - test_power_off_adapter
    - test_reset_on_adapter
    - test_reset_off_adapter
    - test_UUIDs
    - test_start_discovery
    - test_stop_discovery
    - test_discoverable
    - test_nondiscoverable
    - test_pairable
    - test_nonpairable
    """
    version = 1
    ADAPTER_POWER_STATE_TIMEOUT_SECS = 5
    ADAPTER_ACTION_SLEEP_SECS = 1

    # hci0 is the default hci device if there is no external bluetooth dongle.
    EXPECTED_HCI = 'hci0'

    # Supported profiles by chrome os devices
    SUPPORTED_UUIDS = {
            'HSP_AG_UUID': '00001112-0000-1000-8000-00805f9b34fb',
            'GATT_UUID': '00001801-0000-1000-8000-00805f9b34fb',
            'A2DP_SOURCE_UUID': '0000110a-0000-1000-8000-00805f9b34fb',
            'HFP_AG_UUID': '0000111f-0000-1000-8000-00805f9b34fb',
            'PNP_UUID': '00001200-0000-1000-8000-00805f9b34fb',
            'GAP_UUID': '00001800-0000-1000-8000-00805f9b34fb'}

    @_TestLog
    def test_bluetoothd_running(self):
        """Test that bluetoothd is running."""
        return self.bluetooth_hid_facade.is_bluetoothd_running()


    @_TestLog
    def test_start_bluetoothd(self):
        """Test that bluetoothd could be started successfully."""
        return self.bluetooth_hid_facade.start_bluetoothd()


    @_TestLog
    def test_stop_bluetoothd(self):
        """Test that bluetoothd could be stopped successfully."""
        return self.bluetooth_hid_facade.stop_bluetoothd()


    @_TestLog
    def test_adapter_work_state(self):
        """Test that the bluetooth adapter is in the correct working state.

        This includes that the adapter is detectable, is powered on,
        and its hci device is hci0.
        """
        has_adapter = self.bluetooth_hid_facade.has_adapter()
        is_powered_on = self.bluetooth_hid_facade.is_powered_on()
        hci = self.bluetooth_hid_facade.get_hci() == self.EXPECTED_HCI
        self.results = {
                'has_adapter': has_adapter,
                'is_powered_on': is_powered_on,
                'hci': hci}
        return all(self.results.values())


    @_TestLog
    def test_power_on_adapter(self):
        """Test that the adapter could be powered on successfully."""
        power_on = self.bluetooth_hid_facade.set_powered(True)
        try:
            utils.poll_for_condition(
                    condition=self.bluetooth_hid_facade.is_powered_on,
                    timeout=self.ADAPTER_POWER_STATE_TIMEOUT_SECS,
                    desc='Waiting for adapter powered on')
            is_powered_on = True
        except utils.TimeoutError:
            is_powered_on = False
            logging.error('Time out waiting for test_power_on_adapter')

        self.results = {'power_on': power_on, 'is_powered_on': is_powered_on}
        return all(self.results.values())


    @_TestLog
    def test_power_off_adapter(self):
        """Test that the adapter could be powered off successfully."""
        power_off = self.bluetooth_hid_facade.set_powered(False)
        try:
            utils.poll_for_condition(
                    condition=(lambda:
                               not self.bluetooth_hid_facade.is_powered_on()),
                    timeout=self.ADAPTER_POWER_STATE_TIMEOUT_SECS,
                    desc='Waiting for adapter powered off')
            is_powered_off = True
        except utils.TimeoutError:
            is_powered_off = False
            logging.error('Time out waiting for test_power_off_adapter')

        self.results = {
                'power_off': power_off,
                'is_powered_off': is_powered_off}
        return all(self.results.values())


    @_TestLog
    def test_reset_on_adapter(self):
        """Test that the adapter could be reset on successfully.

        This includes restarting bluetoothd, and removing the settings
        and cached devices.
        """
        reset_on = self.bluetooth_hid_facade.reset_on()
        try:
            utils.poll_for_condition(
                    condition=self.bluetooth_hid_facade.is_powered_on,
                    timeout=self.ADAPTER_POWER_STATE_TIMEOUT_SECS,
                    desc='Waiting for adapter reset on')
            is_powered_on = True
        except utils.TimeoutError:
            is_powered_on = False
            logging.error('Time out waiting for test_reset_on_adapter.')

        self.results = {'reset_on': reset_on, 'is_powered_on': is_powered_on}
        return all(self.results.values())


    @_TestLog
    def test_reset_off_adapter(self):
        """Test that the adapter could be reset off successfully.

        This includes restarting bluetoothd, and removing the settings
        and cached devices.
        """
        reset_off = self.bluetooth_hid_facade.reset_off()
        try:
            utils.poll_for_condition(
                    condition=(lambda:
                               not self.bluetooth_hid_facade.is_powered_on()),
                    timeout=self.ADAPTER_POWER_STATE_TIMEOUT_SECS,
                    desc='Waiting for adapter reset off')
            is_powered_off = True
        except utils.TimeoutError:
            is_powered_off = False
            logging.error('Time out waiting for test_reset_off_adapter')

        self.results = {
                'reset_off': reset_off,
                'is_powered_off': is_powered_off}
        return all(self.results.values())


    @_TestLog
    def test_UUIDs(self):
        """Test that basic profiles are supported."""
        adapter_UUIDs = self.bluetooth_hid_facade.get_UUIDs()
        self.results = [uuid for uuid in self.SUPPORTED_UUIDS.values()
                        if uuid not in adapter_UUIDs]
        return not bool(self.results)


    @_TestLog
    def test_start_discovery(self):
        """Test that the adapter could start discovery."""
        start_discovery = self.bluetooth_hid_facade.start_discovery()
        time.sleep(self.ADAPTER_ACTION_SLEEP_SECS)
        is_discovering = self.bluetooth_hid_facade.is_discovering()
        self.results = {
                'start_discovery': start_discovery,
                'is_discovering': is_discovering}
        return all(self.results.values())


    @_TestLog
    def test_stop_discovery(self):
        """Test that the adapter could stop discovery."""
        stop_discovery = self.bluetooth_hid_facade.stop_discovery()
        time.sleep(self.ADAPTER_ACTION_SLEEP_SECS)
        is_not_discovering = not self.bluetooth_hid_facade.is_discovering()
        self.results = {
                'stop_discovery': stop_discovery,
                'is_not_discovering': is_not_discovering}
        return all(self.results.values())


    @_TestLog
    def test_discoverable(self):
        """Test that the adapter could be set discoverable."""
        set_discoverable = self.bluetooth_hid_facade.set_discoverable(True)
        time.sleep(self.ADAPTER_ACTION_SLEEP_SECS)
        is_discoverable = self.bluetooth_hid_facade.is_discoverable()
        self.results = {
                'set_discoverable': set_discoverable,
                'is_discoverable': is_discoverable}
        return all(self.results.values())


    @_TestLog
    def test_nondiscoverable(self):
        """Test that the adapter could be set non-discoverable."""
        set_nondiscoverable = self.bluetooth_hid_facade.set_discoverable(False)
        time.sleep(self.ADAPTER_ACTION_SLEEP_SECS)
        is_nondiscoverable = not self.bluetooth_hid_facade.is_discoverable()
        self.results = {
                'set_nondiscoverable': set_nondiscoverable,
                'is_nondiscoverable': is_nondiscoverable}
        return all(self.results.values())


    @_TestLog
    def test_pairable(self):
        """Test that the adapter could be set pairable."""
        set_pairable = self.bluetooth_hid_facade.set_pairable(True)
        time.sleep(self.ADAPTER_ACTION_SLEEP_SECS)
        is_pairable = self.bluetooth_hid_facade.is_pairable()
        self.results = {
                'set_pairable': set_pairable,
                'is_pairable': is_pairable}
        return all(self.results.values())


    @_TestLog
    def test_nonpairable(self):
        """Test that the adapter could be set non-pairable."""
        set_nonpairable = self.bluetooth_hid_facade.set_pairable(False)
        time.sleep(self.ADAPTER_ACTION_SLEEP_SECS)
        is_nonpairable = not self.bluetooth_hid_facade.is_pairable()
        self.results = {
                'set_nonpairable': set_nonpairable,
                'is_nonpairable': is_nonpairable}
        return all(self.results.values())


    def run_once(self, host):
        """Running Bluetooth basic audio tests

        @param host: device under test host
        """
        factory = remote_facade_factory.RemoteFacadeFactory(host)
        self.bluetooth_hid_facade = factory.create_bluetooth_hid_facade()

        # Run through every tests and collect failed tests in self.fails.
        self.fails = []

        # If a test depends on multiple conditions, write the results of
        # the conditions in self.results so that it is easy to know
        # what conditions failed in the log.
        self.results = None

        # The bluetoothd must be running in the beginning.
        self.test_bluetoothd_running()

        # It is possible that the adapter is not powered on yet.
        # Power it on anyway and verify that it is actually powered on.
        self.test_power_on_adapter()

        # Verify that the adapter could be powered off and powered on,
        # and that it is in the correct working state.
        self.test_power_off_adapter()
        self.test_power_on_adapter()
        self.test_adapter_work_state()

        # Verify that the bluetoothd could be simply stopped and then
        # be started again, and that it is in the correct working state.
        self.test_stop_bluetoothd()
        self.test_start_bluetoothd()
        self.test_adapter_work_state()

        # Verify that the adapter could be reset off and on which includes
        # removing all cached information.
        self.test_reset_off_adapter()
        self.test_reset_on_adapter()
        self.test_adapter_work_state()

        # Verify that the adapter supports basic profiles.
        self.test_UUIDs()

        # Verify that the adapter could start and stop discovery.
        self.test_start_discovery()
        self.test_stop_discovery()
        self.test_start_discovery()

        # Verify that the adapter could set discoverable and non-discoverable.
        self.test_discoverable()
        self.test_nondiscoverable()
        self.test_discoverable()

        # Verify that the adapter could set pairable and non-pairable.
        self.test_pairable()
        self.test_nonpairable()
        self.test_pairable()

        if self.fails:
            raise error.TestFail(self.fails)
