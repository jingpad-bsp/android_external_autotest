# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Server side bluetooth adapter subtests."""

import functools
import logging
import time

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.server import test
from autotest_lib.server.cros.multimedia import remote_facade_factory


# Delay binding the methods since host is only available at run time.
SUPPORTED_DEVICE_TYPES = {
        'MOUSE': lambda host: host.chameleon.get_bluetooh_hid_mouse}

def get_bluetooth_emulated_device(host, device_type):
    """Get the bluetooth emulated device object.

    @param host: the DUT, usually a chromebook
    @param device_type : the bluetooth HID device type, e.g., 'MOUSE'

    @returns: the bluetooth device object

    """
    if device_type not in SUPPORTED_DEVICE_TYPES:
        raise error.TestError('The device type is not supported: %s',
                              device_type)

    # Get the device object and query some important properties.
    device = SUPPORTED_DEVICE_TYPES[device_type](host)()
    device.Init()
    device.name = device.GetChipName()
    device.address = device.GetLocalBluetoothAddress()
    device.pin = device.GetPinCode()
    device.class_of_service = device.GetClassOfService()
    device.class_of_device = device.GetClassOfDevice()
    device.device_type = device.GetHIDDeviceType()
    device.authenticaiton_mode = device.GetAuthenticationMode()
    device.port = device.GetPort()

    logging.info('device type: %s', device_type)
    logging.info('device name: %s', device.name)
    logging.info('address: %s', device.address)
    logging.info('pin: %s', device.pin)
    logging.info('class of service: 0x%04X', device.class_of_service)
    logging.info('class of device: 0x%04X', device.class_of_device)
    logging.info('device type: %s', device.device_type)
    logging.info('authenticaiton mode: %s', device.authenticaiton_mode)
    logging.info('serial port: %s\n', device.port)

    return device


def _TestLog(func):
    """A decorator that logs the test reuslts and collects error messages."""
    @functools.wraps(func)
    def wrapper(instance, *args, **kwargs):
        """A wrapper of the decorated method."""
        instance.results = None
        test_result = func(instance, *args, **kwargs)
        if test_result:
            logging.info('[*** passed: %s]', func.__name__)
        else:
            fail_msg = '[--- failed: %s (%s)]' % (func.__name__,
                                            str(instance.results))
            logging.error(fail_msg)
            instance.fails.append(fail_msg)
        return test_result
    return wrapper


class BluetoothAdapterTests(test.test):
    """Server side bluetooth adapter tests.

    This test class tries to thoroughly verify most of the important work
    states of a bluetooth adapter.

    The various test methods are supposed to be invoked by actual autotest
    tests such as server/cros/site_tests/bluetooth_Adapter*.

    """
    version = 1
    ADAPTER_POWER_STATE_TIMEOUT_SECS = 5
    ADAPTER_ACTION_SLEEP_SECS = 1
    ADAPTER_PAIRING_TIMEOUT_SECS = 60
    ADAPTER_CONNECTION_TIMEOUT_SECS = 15
    ADAPTER_DISCONNECTION_TIMEOUT_SECS = 15
    ADAPTER_PAIRING_POLLING_SLEEP_SECS = 3
    ADAPTER_DISCOVER_TIMEOUT_SECS = 60          # 30 seconds too short sometimes
    ADAPTER_DISCOVER_POLLING_SLEEP_SECS = 1
    ADAPTER_DISCOVER_NAME_TIMEOUT_SECS = 30

    # hci0 is the default hci device if there is no external bluetooth dongle.
    EXPECTED_HCI = 'hci0'

    CLASS_OF_SERVICE_MASK = 0xFFE000
    CLASS_OF_DEVICE_MASK = 0x001FFF

    # Supported profiles by chrome os.
    SUPPORTED_UUIDS = {
            'HSP_AG_UUID': '00001112-0000-1000-8000-00805f9b34fb',
            'GATT_UUID': '00001801-0000-1000-8000-00805f9b34fb',
            'A2DP_SOURCE_UUID': '0000110a-0000-1000-8000-00805f9b34fb',
            'HFP_AG_UUID': '0000111f-0000-1000-8000-00805f9b34fb',
            'PNP_UUID': '00001200-0000-1000-8000-00805f9b34fb',
            'GAP_UUID': '00001800-0000-1000-8000-00805f9b34fb'}


    def get_device(self, host, device_type):
        """Get the bluetooth device object.

        @param host: the DUT, usually a chromebook
        @param device_type : the bluetooth HID device type, e.g., 'MOUSE'

        @returns: the bluetooth device object

        """
        if self.devices[device_type] is None:
            self.devices[device_type] = get_bluetooth_emulated_device(
                    host, device_type)
        return self.devices[device_type]


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
        is_powered_on = False
        try:
            utils.poll_for_condition(
                    condition=self.bluetooth_hid_facade.is_powered_on,
                    timeout=self.ADAPTER_POWER_STATE_TIMEOUT_SECS,
                    desc='Waiting for adapter powered on')
            is_powered_on = True
        except utils.TimeoutError as e:
            logging.error('test_power_on_adapter: %s', e)
        except:
            logging.error('test_power_on_adapter: unpredicted error')

        self.results = {'power_on': power_on, 'is_powered_on': is_powered_on}
        return all(self.results.values())


    @_TestLog
    def test_power_off_adapter(self):
        """Test that the adapter could be powered off successfully."""
        power_off = self.bluetooth_hid_facade.set_powered(False)
        is_powered_off = False
        try:
            utils.poll_for_condition(
                    condition=(lambda:
                               not self.bluetooth_hid_facade.is_powered_on()),
                    timeout=self.ADAPTER_POWER_STATE_TIMEOUT_SECS,
                    desc='Waiting for adapter powered off')
            is_powered_off = True
        except utils.TimeoutError as e:
            logging.error('test_power_off_adapter: %s', e)
        except:
            logging.error('test_power_off_adapter: unpredicted error')

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
        is_powered_on = False
        try:
            utils.poll_for_condition(
                    condition=self.bluetooth_hid_facade.is_powered_on,
                    timeout=self.ADAPTER_POWER_STATE_TIMEOUT_SECS,
                    desc='Waiting for adapter reset on')
            is_powered_on = True
        except utils.TimeoutError as e:
            logging.error('test_reset_on_adapter: %s', e)
        except:
            logging.error('test_reset_on_adapter: unpredicted error')

        self.results = {'reset_on': reset_on, 'is_powered_on': is_powered_on}
        return all(self.results.values())


    @_TestLog
    def test_reset_off_adapter(self):
        """Test that the adapter could be reset off successfully.

        This includes restarting bluetoothd, and removing the settings
        and cached devices.
        """
        reset_off = self.bluetooth_hid_facade.reset_off()
        is_powered_off = False
        try:
            utils.poll_for_condition(
                    condition=(lambda:
                               not self.bluetooth_hid_facade.is_powered_on()),
                    timeout=self.ADAPTER_POWER_STATE_TIMEOUT_SECS,
                    desc='Waiting for adapter reset off')
            is_powered_off = True
        except utils.TimeoutError as e:
            logging.error('test_reset_off_adapter: %s', e)
        except:
            logging.error('test_reset_off_adapter: unpredicted error')

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


    @_TestLog
    def test_discover_device(self, device_address):
        """Test that the adapter could discover the specified device address.

        @param device_address: Address of the device.

        @returns: True if the device is found. False otherwise.

        """
        has_device_initially = False
        start_discovery = False
        device_discovered = False
        has_device = self.bluetooth_hid_facade.has_device

        if has_device(device_address):
            has_device_initially = True
        elif self.bluetooth_hid_facade.start_discovery():
            start_discovery = True
            try:
                utils.poll_for_condition(
                        condition=(lambda: has_device(device_address)),
                        timeout=self.ADAPTER_DISCOVER_TIMEOUT_SECS,
                        sleep_interval=self.ADAPTER_DISCOVER_POLLING_SLEEP_SECS,
                        desc='Waiting for discovering %s' % device_address)
                device_discovered = True
            except utils.TimeoutError as e:
                logging.error('test_discover_device: %s', e)
            except:
                logging.error('test_discover_device: unpredicted error')

        self.results = {
                'has_device_initially': has_device_initially,
                'start_discovery': start_discovery,
                'device_discovered': device_discovered}
        return has_device_initially or device_discovered


    @_TestLog
    def test_pairing(self, device_address, pin, trusted=True):
        """Test that the adapter could pair with the device successfully.

        @param device_address: Address of the device.
        @param pin: pin code to pair with the device.
        @param trusted: indicating whether to set the device trusted.

        @returns: True if pairing succeeds. False otherwise.

        """

        def _pair_device():
            """Pair to the device.

            @returns: True if it could pair with the device. False otherwise.

            """
            return self.bluetooth_hid_facade.pair_legacy_device(
                    device_address, pin, trusted,
                    self.ADAPTER_PAIRING_TIMEOUT_SECS)


        has_device = False
        paired = False
        if self.bluetooth_hid_facade.has_device(device_address):
            has_device = True
            try:
                utils.poll_for_condition(
                        condition=_pair_device,
                        timeout=self.ADAPTER_PAIRING_TIMEOUT_SECS,
                        sleep_interval=self.ADAPTER_PAIRING_POLLING_SLEEP_SECS,
                        desc='Waiting for pairing %s' % device_address)
                paired = True
            except utils.TimeoutError as e:
                logging.error('test_pairing: %s', e)
            except:
                logging.error('test_pairing: unpredicted error')

        self.results = {'has_device': has_device, 'paired': paired}
        return all(self.results.values())


    @_TestLog
    def test_remove_pairing(self, device_address):
        """Test that the adapter could remove the paired device.

        @param device_address: Address of the device.

        @returns: True if the device is removed successfully. False otherwise.

        """
        device_is_paired_initially = self.bluetooth_hid_facade.device_is_paired(
                device_address)
        remove_pairing = False
        pairing_removed = False

        if device_is_paired_initially:
            remove_pairing = self.bluetooth_hid_facade.remove_device_object(
                    device_address)
            pairing_removed = not self.bluetooth_hid_facade.device_is_paired(
                    device_address)

        self.results = {
                'device_is_paired_initially': device_is_paired_initially,
                'remove_pairing': remove_pairing,
                'pairing_removed': pairing_removed}
        return all(self.results.values())


    def test_set_trusted(self, device_address, trusted=True):
        """Test whether the device with the specified address is trusted.

        @param device_address: Address of the device.
        @param trusted : True or False indicating if trusted is expected.

        @returns: True if the device's "Trusted" property is as specified;
                  False otherwise.

        """

        set_trusted = self.bluetooth_hid_facade.set_trusted(
                device_address, trusted)

        properties = self.bluetooth_hid_facade.get_device_properties(
                device_address)
        actual_trusted = properties.get('Trusted')

        self.results = {
                'set_trusted': set_trusted,
                'actual trusted': actual_trusted,
                'expected trusted': trusted}
        return actual_trusted == trusted


    @_TestLog
    def test_connection_by_adapter(self, device_address):
        """Test that the adapter of dut could connect to the device successfully

        It is the caller's responsibility to pair to the device before
        doing connection.

        @param device_address: Address of the device.

        @returns: True if connection is performed. False otherwise.

        """

        def _connect_device():
            """Connect to the device.

            @returns: True if it could connect to the device. False otherwise.

            """
            return self.bluetooth_hid_facade.connect_device(device_address)


        has_device = False
        connected = False
        if self.bluetooth_hid_facade.has_device(device_address):
            has_device = True
            try:
                utils.poll_for_condition(
                        condition=_connect_device,
                        timeout=self.ADAPTER_PAIRING_TIMEOUT_SECS,
                        sleep_interval=self.ADAPTER_PAIRING_POLLING_SLEEP_SECS,
                        desc='Waiting for connecting to %s' % device_address)
                connected = True
            except utils.TimeoutError as e:
                logging.error('test_connection_by_adapter: %s', e)
            except:
                logging.error('test_connection_by_adapter: unpredicted error')

        self.results = {'has_device': has_device, 'connected': connected}
        return all(self.results.values())


    @_TestLog
    def test_disconnection_by_adapter(self, device_address):
        """Test that the adapter of dut could disconnect the device successfully

        @param device_address: Address of the device.

        @returns: True if disconnection is performed. False otherwise.

        """
        return self.bluetooth_hid_facade.disconnect_device(device_address)


    def _enter_command_mode(self, device):
        """Let the device enter command mode.

        Before using the device, need to call this method to make sure
        it is in the command mode.

        @param device: the device object

        """
        try:
            return device.EnterCommandMode()
        except Exception as e:
            return False


    @_TestLog
    def test_connection_by_device(self, device):
        """Test that the device could connect to the adapter successfully.

        This emulates the behavior that a device may initiate a
        connection request after waking up from power saving mode.

        @param device: the device object such as a mouse or keyboard.

        @returns: True if connection is performed correctly by device and
                  the adapter also enters connection state.
                  False otherwise.

        """
        enter_command_mode = self._enter_command_mode(device)

        connection_by_device = False
        adapter_address = self.bluetooth_hid_facade.address
        try:
            device.ConnectToRemoteAddress(adapter_address)
            connection_by_device = True
        except Exception as e:
            logging.error('test_connection_by_device: %s', e)
        except:
            logging.error('test_connection_by_device: unpredicted error')

        connection_seen_by_adapter = False
        device_is_connected = self.bluetooth_hid_facade.device_is_connected
        try:
            utils.poll_for_condition(
                    condition=lambda: device_is_connected(device.address),
                    timeout=self.ADAPTER_CONNECTION_TIMEOUT_SECS,
                    desc='Waiting for connection from %s' % device.address)
            connection_seen_by_adapter = True
        except utils.TimeoutError as e:
            logging.error('test_connection_by_device: %s', e)
        except:
            logging.error('test_connection_by_device: unpredicted error')

        self.results = {
                'enter_command_mode': enter_command_mode,
                'connection_by_device': connection_by_device,
                'connection_seen_by_adapter': connection_seen_by_adapter}
        return all(self.results.values())


    @_TestLog
    def test_disconnection_by_device(self, device):
        """Test that the device could disconnect the adapter successfully.

        This emulates the behavior that a device may initiate a
        disconnection request before going into power saving mode.

        @param device: the device object such as a mouse or keyboard.

        @returns: True if disconnection is performed correctly by device and
                  the adapter also observes the disconnection.
                  False otherwise.

        """
        disconnection_by_device = False
        try:
            device.Disconnect()
            disconnection_by_device = True
        except Exception as e:
            logging.error('test_disconnection_by_device: %s', e)
        except:
            logging.error('test_disconnection_by_device: unpredicted error')

        disconnection_seen_by_adapter = False
        device_is_connected = self.bluetooth_hid_facade.device_is_connected
        try:
            utils.poll_for_condition(
                    condition=lambda: not device_is_connected(device.address),
                    timeout=self.ADAPTER_DISCONNECTION_TIMEOUT_SECS,
                    desc='Waiting for disconnection from %s' % device.address)
            disconnection_seen_by_adapter = True
        except utils.TimeoutError as e:
            logging.error('test_disconnection_by_device: %s', e)
        except:
            logging.error('test_disconnection_by_device: unpredicted error')

        self.results = {
                'disconnection_by_device': disconnection_by_device,
                'disconnection_seen_by_adapter': disconnection_seen_by_adapter}
        return all(self.results.values())


    def _get_device_name(self, device_address):
        """Get the device name.

        @returns: True if the device name is derived. None otherwise.

        """
        properties = self.bluetooth_hid_facade.get_device_properties(
                device_address)
        self.discovered_device_name = properties.get('Name')
        return bool(self.discovered_device_name)


    @_TestLog
    def test_device_name(self, device_address, expected_device_name):
        """Test that the device name discovered by the adapter is correct.

        @param device_address: Address of the device.
        @param expected_device_name: the bluetooth device name

        @returns: True if the discovered_device_name is expected_device_name.
                  False otherwise.

        """
        try:
            utils.poll_for_condition(
                    condition=lambda: self._get_device_name(device_address),
                    timeout=self.ADAPTER_DISCOVER_NAME_TIMEOUT_SECS,
                    sleep_interval=self.ADAPTER_DISCOVER_POLLING_SLEEP_SECS,
                    desc='Waiting for device name of %s' % device_address)
        except utils.TimeoutError as e:
            logging.error('test_device_name: %s', e)
        except:
            logging.error('test_device_name: unexpected error')

        self.results = {
                'expected_device_name': expected_device_name,
                'discovered_device_name': self.discovered_device_name}
        return self.discovered_device_name == expected_device_name


    @_TestLog
    def test_device_class_of_service(self, device_address,
                                     expected_class_of_service):
        """Test that the discovered device class of service is as expected.

        @param device_address: Address of the device.
        @param expected_class_of_service: the expected class of service

        @returns: True if the discovered class of service matches the
                  expected class of service. False otherwise.

        """
        properties = self.bluetooth_hid_facade.get_device_properties(
                device_address)
        device_class = properties.get('Class')
        discovered_class_of_service = device_class & self.CLASS_OF_SERVICE_MASK
        self.results = {
                'device_class': device_class,
                'expected_class_of_service': expected_class_of_service,
                'discovered_class_of_service': discovered_class_of_service}
        return discovered_class_of_service == expected_class_of_service


    @_TestLog
    def test_device_class_of_device(self, device_address,
                                    expected_class_of_device):
        """Test that the discovered device class of device is as expected.

        @param device_address: Address of the device.
        @param expected_class_of_device: the expected class of device

        @returns: True if the discovered class of device matches the
                  expected class of device. False otherwise.

        """
        properties = self.bluetooth_hid_facade.get_device_properties(
                device_address)
        device_class = properties.get('Class')
        discovered_class_of_device = device_class & self.CLASS_OF_DEVICE_MASK
        self.results = {
                'device_class': device_class,
                'expected_class_of_device': expected_class_of_device,
                'discovered_class_of_device': discovered_class_of_device}
        return discovered_class_of_device == expected_class_of_device


    def initialize(self):
        """Initialize bluetooth adapter tests."""
        # Run through every tests and collect failed tests in self.fails.
        self.fails = []

        # If a test depends on multiple conditions, write the results of
        # the conditions in self.results so that it is easy to know
        # what conditions failed by looking at the log.
        self.results = None

        # Some tests may instantiate a peripheral device for testing.
        self.devices = dict()
        for device_type in SUPPORTED_DEVICE_TYPES:
            self.devices[device_type] = None


    def run_once(self, *args, **kwargs):
        """This method should be implemented by children classes.

        Typically, the run_once() method would look like:

        factory = remote_facade_factory.RemoteFacadeFactory(host)
        self.bluetooth_hid_facade = factory.create_bluetooth_hid_facade()

        self.test_bluetoothd_running()
        # ...
        # invoke more self.test_xxx() tests.
        # ...

        if self.fails:
            raise error.TestFail(self.fails)

        """
        raise NotImplementedError


    def cleanup(self):
        """Clean up bluetooth adapter tests."""
        # Close the device properly if a device is instantiated.
        # Note: do not write something like the following statements
        #           if self.devices[device_type]:
        #       or
        #           if bool(self.devices[device_type]):
        #       Othereise, it would try to invoke bluetooth_mouse.__nonzero__()
        #       which just does not exist.
        for device_type in SUPPORTED_DEVICE_TYPES:
            if self.devices[device_type] is not None:
                self.devices[device_type].Close()
