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


# Delay binding the methods since host is only available at run time.
SUPPORTED_DEVICE_TYPES = {
        'MOUSE': lambda host: host.chameleon.get_bluetooh_hid_mouse}


def _run_method(method, method_name, *args, **kwargs):
    """Run a target method and capture exceptions if any.

    This is just a wrapper of the target method so that we do not need to
    write the exception capturing structure repeatedly. The method could
    be either a device method or a facade method.

    @param method: the method to run
    @param method_name: the name of the method

    @returns: the return value of target method() if successful.
              False otherwise.

    """
    result = False
    try:
        result = method(*args, **kwargs)
    except Exception as e:
        logging.error('%s: %s', method_name, e)
    except:
        logging.error('%s: unexpected error', method_name)
    return result


def get_bluetooth_emulated_device(host, device_type):
    """Get the bluetooth emulated device object.

    @param host: the DUT, usually a chromebook
    @param device_type : the bluetooth HID device type, e.g., 'MOUSE'

    @returns: the bluetooth device object

    """

    def _retry_device_method(method_name):
        """retry the emulated device's method.

        The method is invoked as device.xxxx() e.g., device.GetChipName().

        Note that the method name string is provided to get the device's actual
        method object at run time through getattr(). The rebinding is required
        because a new device may have been created previously or during the
        execution of fix_serial_device().

        Given a device's method, it is not feasible to get the method name
        through __name__ attribute. This limitation is due to the fact that
        the device is a dotted object of an XML RPC server proxy.
        As an example, with the method name 'GetChipName', we could derive the
        correspoinding method device.GetChipName. On the contrary, given
        device.GetChipName, it is not feasible to get the method name by
        device.GetChipName.__name__

        Also note that if the device method fails at the first time, we would
        try to fix the problem by re-creating the serial device and see if the
        problem is fixed. If not, we will reboot the chameleon board and see
        if the problem is fixed. If yes, execute the target method the second
        time.

        @param method_name: the string of the method name.

        @returns: the result returned by the device's method.

        """
        result = _run_method(getattr(device, method_name), method_name)
        if _is_successful(result):
            return result

        logging.error('%s failed the 1st time. Try to fix the serial device.',
                      method_name)

        # Try to fix the serial device if possible.
        if not fix_serial_device(host, device):
            return False

        logging.info('%s: retry the 2nd time.', method_name)
        return _run_method(getattr(device, method_name), method_name)


    if device_type not in SUPPORTED_DEVICE_TYPES:
        raise error.TestError('The device type is not supported: %s',
                              device_type)

    # Get the bluetooth device object and query some important properties.
    device = SUPPORTED_DEVICE_TYPES[device_type](host)()

    _retry_device_method('Init')
    logging.info('device type: %s', device_type)

    device.name = _retry_device_method('GetChipName')
    logging.info('device name: %s', device.name)

    device.address = _retry_device_method('GetLocalBluetoothAddress')
    logging.info('address: %s', device.address)

    device.pin = _retry_device_method('GetPinCode')
    logging.info('pin: %s', device.pin)

    device.class_of_service = _retry_device_method('GetClassOfService')
    logging.info('class of service: 0x%04X', device.class_of_service)

    device.class_of_device = _retry_device_method('GetClassOfDevice')
    logging.info('class of device: 0x%04X', device.class_of_device)

    device.device_type = _retry_device_method('GetHIDDeviceType')
    logging.info('device type: %s', device.device_type)

    device.authenticaiton_mode = _retry_device_method('GetAuthenticationMode')
    logging.info('authentication mode: %s', device.authenticaiton_mode)

    device.port = _retry_device_method('GetPort')
    logging.info('serial port: %s\n', device.port)

    return device


def recreate_serial_device(device):
    """Create and connect to a new serial device.

    @param device: the bluetooth HID device

    @returns: True if the serial device is re-created successfully.

    """
    logging.info('Remove the old serial device and create a new one.')
    if device is not None:
        try:
            device.Close()
        except:
            logging.error('failed to close the serial device.')
            return False
    try:
        device.CreateSerialDevice()
        return True
    except:
        logging.error('failed to invoke CreateSerialDevice.')
        return False


def _reboot_chameleon(host, device):
    REBOOT_SLEEP_SECS = 40

    # Close the bluetooth peripheral device and reboot the chameleon board.
    device.Close()
    logging.info('rebooting chameleon...')
    host.chameleon.reboot()

    # Every chameleon reboot would take a bit more than REBOOT_SLEEP_SECS.
    # Sleep REBOOT_SLEEP_SECS and then begin probing the chameleon board.
    time.sleep(REBOOT_SLEEP_SECS)

    # Check if the serial device could initialize, connect, and
    # enter command mode correctly.
    logging.info('Checking device status...')
    if not _run_method(device.Init, 'Init'):
        logging.info('device.Init: failed after reboot')
        return False
    if not device.CheckSerialConnection():
        logging.info('device.CheckSerialConnection: failed after reboot')
        return False
    if not _run_method(device.EnterCommandMode, 'EnterCommandMode'):
        logging.info('device.EnterCommandMode: failed after reboot')
        return False
    logging.info('The device is created successfully after reboot.')
    return True


def _is_successful(result):
    """Is the method result successful?

    @param result: a method result

    @returns: True if bool(result) is True or result is 0.
              Some method result, e.g., class_of_service, may be 0
              which is considered a valid result.

    """
    return bool(result) or result is 0


def fix_serial_device(host, device):
    """Fix the serial device.

    This function tries to fix the serial device by
    (1) re-creating a serial device, or
    (2) rebooting the chameleon board.

    @param host: the DUT, usually a chromebook
    @param device: the bluetooth HID device

    @returns: True if the serial device is fixed. False otherwise.

    """
    # Check the serial connection. Fix it if needed.
    if device.CheckSerialConnection():
        # The USB serial connection still exists.
        # Re-connection suffices to solve the problem. The problem
        # is usually caused by serial port change. For example,
        # the serial port changed from /dev/ttyUSB0 to /dev/ttyUSB1.
        logging.info('retry: creating a new serial device...')
        if not recreate_serial_device(device):
            return False

    # Check if recreate_serial_device() above fixes the problem.
    # If not, reboot the chameleon board including creation of a new
    # bluetooth device. Check if reboot fixes the problem.
    # If not, return False.
    result = _run_method(device.EnterCommandMode, 'EnterCommandMode')
    return _is_successful(result) or _reboot_chameleon(host, device)


def retry(test_method, instance, *args, **kwargs):
    """Execute the target facade test_method(). Retry if failing the first time.

    A test_method is something like self.test_xxxx() in BluetoothAdapterTests,
    e.g., BluetoothAdapterTests.test_bluetoothd_running().

    @param test_method: the test method to retry

    @returns: True if the return value of test_method() is successful.
              False otherwise.

    """
    if _is_successful(_run_method(test_method, test_method.__name__,
                                  instance, *args, **kwargs)):
        return True

    # Try to fix the serial device if applicable.
    logging.error('%s failed at the 1st time.', test_method.__name__)

    # If this test does not use any attached serial device, just re-run
    # the test.
    logging.info('%s: retry the 2nd time.', test_method.__name__)
    time.sleep(1)
    if not hasattr(instance, 'device_type'):
        return _is_successful(_run_method(test_method, test_method.__name__,
                                          instance, *args, **kwargs))

    host = instance.host
    device = instance.devices[instance.device_type]
    if not fix_serial_device(host, device):
        return False

    logging.info('%s: retry the 2nd time.', test_method.__name__)
    return _is_successful(_run_method(test_method, test_method.__name__,
                                      instance, *args, **kwargs))


def _test_retry_and_log(test_method_or_retry_flag):
    """A decorator that logs test results, collects error messages, and retries
       on request.

    @param test_method_or_retry_flag: either the test_method or a retry_flag.
        There are some possibilities of this argument:
        1. the test_method to conduct and retry: should retry the test_method.
            This occurs with
            @_test_retry_and_log
        2. the retry flag is True. Should retry the test_method.
            This occurs with
            @_test_retry_and_log(True)
        3. the retry flag is False. Do not retry the test_method.
            This occurs with
            @_test_retry_and_log(False)

    @returns: a wrapper of the test_method with test log. The retry mechanism
        would depend on the retry flag.

    """

    def decorator(test_method):
        """A decorator wrapper of the decorated test_method.

        @param test_method: the test method being decorated.

        @returns the wrapper of the test method.

        """
        @functools.wraps(test_method)
        def wrapper(instance, *args, **kwargs):
            """A wrapper of the decorated method.

            @param instance: an BluetoothAdapterTests instance

            @returns the result of the test method

            """
            instance.results = None
            if callable(test_method_or_retry_flag) or test_method_or_retry_flag:
                test_result = retry(test_method, instance, *args, **kwargs)
            else:
                test_result = test_method(instance, *args, **kwargs)

            if test_result:
                logging.info('[*** passed: %s]', test_method.__name__)
            else:
                fail_msg = '[--- failed: %s (%s)]' % (test_method.__name__,
                                                      str(instance.results))
                logging.error(fail_msg)
                instance.fails.append(fail_msg)
            return test_result
        return wrapper

    if callable(test_method_or_retry_flag):
        # If the decorator function comes with no argument like
        # @_test_retry_and_log
        return decorator(test_method_or_retry_flag)
    else:
        # If the decorator function comes with an argument like
        # @_test_retry_and_log(False)
        return decorator


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
    ADAPTER_CONNECTION_TIMEOUT_SECS = 30
    ADAPTER_DISCONNECTION_TIMEOUT_SECS = 30
    ADAPTER_PAIRING_POLLING_SLEEP_SECS = 3
    ADAPTER_DISCOVER_TIMEOUT_SECS = 60          # 30 seconds too short sometimes
    ADAPTER_DISCOVER_POLLING_SLEEP_SECS = 1
    ADAPTER_DISCOVER_NAME_TIMEOUT_SECS = 30

    # hci0 is the default hci device if there is no external bluetooth dongle.
    EXPECTED_HCI = 'hci0'

    CLASS_OF_SERVICE_MASK = 0xFFE000
    CLASS_OF_DEVICE_MASK = 0x001FFF

    # Constants about advertising.
    DAFAULT_MIN_ADVERTISEMENT_INTERVAL_MS = 1280
    DAFAULT_MAX_ADVERTISEMENT_INTERVAL_MS = 1280
    ADVERTISING_INTERVAL_UNIT = 0.625

    # Supported profiles by chrome os.
    SUPPORTED_UUIDS = {
            'HSP_AG_UUID': '00001112-0000-1000-8000-00805f9b34fb',
            'GATT_UUID': '00001801-0000-1000-8000-00805f9b34fb',
            'A2DP_SOURCE_UUID': '0000110a-0000-1000-8000-00805f9b34fb',
            'HFP_AG_UUID': '0000111f-0000-1000-8000-00805f9b34fb',
            'PNP_UUID': '00001200-0000-1000-8000-00805f9b34fb',
            'GAP_UUID': '00001800-0000-1000-8000-00805f9b34fb'}


    def get_device(self, device_type):
        """Get the bluetooth device object.

        @param device_type : the bluetooth HID device type, e.g., 'MOUSE'

        @returns: the bluetooth device object

        """
        self.device_type = device_type
        if self.devices[device_type] is None:
            self.devices[device_type] = get_bluetooth_emulated_device(
                    self.host, device_type)
        return self.devices[device_type]


    @_test_retry_and_log
    def test_bluetoothd_running(self):
        """Test that bluetoothd is running."""
        return self.bluetooth_facade.is_bluetoothd_running()


    @_test_retry_and_log
    def test_start_bluetoothd(self):
        """Test that bluetoothd could be started successfully."""
        return self.bluetooth_facade.start_bluetoothd()


    @_test_retry_and_log
    def test_stop_bluetoothd(self):
        """Test that bluetoothd could be stopped successfully."""
        return self.bluetooth_facade.stop_bluetoothd()


    @_test_retry_and_log
    def test_adapter_work_state(self):
        """Test that the bluetooth adapter is in the correct working state.

        This includes that the adapter is detectable, is powered on,
        and its hci device is hci0.
        """
        has_adapter = self.bluetooth_facade.has_adapter()
        is_powered_on = self.bluetooth_facade.is_powered_on()
        hci = self.bluetooth_facade.get_hci() == self.EXPECTED_HCI
        self.results = {
                'has_adapter': has_adapter,
                'is_powered_on': is_powered_on,
                'hci': hci}
        return all(self.results.values())


    @_test_retry_and_log
    def test_power_on_adapter(self):
        """Test that the adapter could be powered on successfully."""
        power_on = self.bluetooth_facade.set_powered(True)
        is_powered_on = False
        try:
            utils.poll_for_condition(
                    condition=self.bluetooth_facade.is_powered_on,
                    timeout=self.ADAPTER_POWER_STATE_TIMEOUT_SECS,
                    desc='Waiting for adapter powered on')
            is_powered_on = True
        except utils.TimeoutError as e:
            logging.error('test_power_on_adapter: %s', e)
        except:
            logging.error('test_power_on_adapter: unexpected error')

        self.results = {'power_on': power_on, 'is_powered_on': is_powered_on}
        return all(self.results.values())


    @_test_retry_and_log
    def test_power_off_adapter(self):
        """Test that the adapter could be powered off successfully."""
        power_off = self.bluetooth_facade.set_powered(False)
        is_powered_off = False
        try:
            utils.poll_for_condition(
                    condition=(lambda:
                               not self.bluetooth_facade.is_powered_on()),
                    timeout=self.ADAPTER_POWER_STATE_TIMEOUT_SECS,
                    desc='Waiting for adapter powered off')
            is_powered_off = True
        except utils.TimeoutError as e:
            logging.error('test_power_off_adapter: %s', e)
        except:
            logging.error('test_power_off_adapter: unexpected error')

        self.results = {
                'power_off': power_off,
                'is_powered_off': is_powered_off}
        return all(self.results.values())


    @_test_retry_and_log
    def test_reset_on_adapter(self):
        """Test that the adapter could be reset on successfully.

        This includes restarting bluetoothd, and removing the settings
        and cached devices.
        """
        reset_on = self.bluetooth_facade.reset_on()
        is_powered_on = False
        try:
            utils.poll_for_condition(
                    condition=self.bluetooth_facade.is_powered_on,
                    timeout=self.ADAPTER_POWER_STATE_TIMEOUT_SECS,
                    desc='Waiting for adapter reset on')
            is_powered_on = True
        except utils.TimeoutError as e:
            logging.error('test_reset_on_adapter: %s', e)
        except:
            logging.error('test_reset_on_adapter: unexpected error')

        self.results = {'reset_on': reset_on, 'is_powered_on': is_powered_on}
        return all(self.results.values())


    @_test_retry_and_log
    def test_reset_off_adapter(self):
        """Test that the adapter could be reset off successfully.

        This includes restarting bluetoothd, and removing the settings
        and cached devices.
        """
        reset_off = self.bluetooth_facade.reset_off()
        is_powered_off = False
        try:
            utils.poll_for_condition(
                    condition=(lambda:
                               not self.bluetooth_facade.is_powered_on()),
                    timeout=self.ADAPTER_POWER_STATE_TIMEOUT_SECS,
                    desc='Waiting for adapter reset off')
            is_powered_off = True
        except utils.TimeoutError as e:
            logging.error('test_reset_off_adapter: %s', e)
        except:
            logging.error('test_reset_off_adapter: unexpected error')

        self.results = {
                'reset_off': reset_off,
                'is_powered_off': is_powered_off}
        return all(self.results.values())


    @_test_retry_and_log
    def test_UUIDs(self):
        """Test that basic profiles are supported."""
        adapter_UUIDs = self.bluetooth_facade.get_UUIDs()
        self.results = [uuid for uuid in self.SUPPORTED_UUIDS.values()
                        if uuid not in adapter_UUIDs]
        return not bool(self.results)


    @_test_retry_and_log
    def test_start_discovery(self):
        """Test that the adapter could start discovery."""
        start_discovery = self.bluetooth_facade.start_discovery()
        time.sleep(self.ADAPTER_ACTION_SLEEP_SECS)
        is_discovering = self.bluetooth_facade.is_discovering()
        self.results = {
                'start_discovery': start_discovery,
                'is_discovering': is_discovering}
        return all(self.results.values())


    @_test_retry_and_log
    def test_stop_discovery(self):
        """Test that the adapter could stop discovery."""
        stop_discovery = self.bluetooth_facade.stop_discovery()
        time.sleep(self.ADAPTER_ACTION_SLEEP_SECS)
        is_not_discovering = not self.bluetooth_facade.is_discovering()
        self.results = {
                'stop_discovery': stop_discovery,
                'is_not_discovering': is_not_discovering}
        return all(self.results.values())


    @_test_retry_and_log
    def test_discoverable(self):
        """Test that the adapter could be set discoverable."""
        set_discoverable = self.bluetooth_facade.set_discoverable(True)
        time.sleep(self.ADAPTER_ACTION_SLEEP_SECS)
        is_discoverable = self.bluetooth_facade.is_discoverable()
        self.results = {
                'set_discoverable': set_discoverable,
                'is_discoverable': is_discoverable}
        return all(self.results.values())


    @_test_retry_and_log
    def test_nondiscoverable(self):
        """Test that the adapter could be set non-discoverable."""
        set_nondiscoverable = self.bluetooth_facade.set_discoverable(False)
        time.sleep(self.ADAPTER_ACTION_SLEEP_SECS)
        is_nondiscoverable = not self.bluetooth_facade.is_discoverable()
        self.results = {
                'set_nondiscoverable': set_nondiscoverable,
                'is_nondiscoverable': is_nondiscoverable}
        return all(self.results.values())


    @_test_retry_and_log
    def test_pairable(self):
        """Test that the adapter could be set pairable."""
        set_pairable = self.bluetooth_facade.set_pairable(True)
        time.sleep(self.ADAPTER_ACTION_SLEEP_SECS)
        is_pairable = self.bluetooth_facade.is_pairable()
        self.results = {
                'set_pairable': set_pairable,
                'is_pairable': is_pairable}
        return all(self.results.values())


    @_test_retry_and_log
    def test_nonpairable(self):
        """Test that the adapter could be set non-pairable."""
        set_nonpairable = self.bluetooth_facade.set_pairable(False)
        time.sleep(self.ADAPTER_ACTION_SLEEP_SECS)
        is_nonpairable = not self.bluetooth_facade.is_pairable()
        self.results = {
                'set_nonpairable': set_nonpairable,
                'is_nonpairable': is_nonpairable}
        return all(self.results.values())


    @_test_retry_and_log
    def test_discover_device(self, device_address):
        """Test that the adapter could discover the specified device address.

        @param device_address: Address of the device.

        @returns: True if the device is found. False otherwise.

        """
        has_device_initially = False
        start_discovery = False
        device_discovered = False
        has_device = self.bluetooth_facade.has_device

        if has_device(device_address):
            has_device_initially = True
        elif self.bluetooth_facade.start_discovery():
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
                logging.error('test_discover_device: unexpected error')

        self.results = {
                'has_device_initially': has_device_initially,
                'start_discovery': start_discovery,
                'device_discovered': device_discovered}
        return has_device_initially or device_discovered


    @_test_retry_and_log
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
            return self.bluetooth_facade.pair_legacy_device(
                    device_address, pin, trusted,
                    self.ADAPTER_PAIRING_TIMEOUT_SECS)


        has_device = False
        paired = False
        if self.bluetooth_facade.has_device(device_address):
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
                logging.error('test_pairing: unexpected error')

        self.results = {'has_device': has_device, 'paired': paired}
        return all(self.results.values())


    @_test_retry_and_log
    def test_remove_pairing(self, device_address):
        """Test that the adapter could remove the paired device.

        @param device_address: Address of the device.

        @returns: True if the device is removed successfully. False otherwise.

        """
        device_is_paired_initially = self.bluetooth_facade.device_is_paired(
                device_address)
        remove_pairing = False
        pairing_removed = False

        if device_is_paired_initially:
            remove_pairing = self.bluetooth_facade.remove_device_object(
                    device_address)
            pairing_removed = not self.bluetooth_facade.device_is_paired(
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

        set_trusted = self.bluetooth_facade.set_trusted(
                device_address, trusted)

        properties = self.bluetooth_facade.get_device_properties(
                device_address)
        actual_trusted = properties.get('Trusted')

        self.results = {
                'set_trusted': set_trusted,
                'actual trusted': actual_trusted,
                'expected trusted': trusted}
        return actual_trusted == trusted


    @_test_retry_and_log
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
            return self.bluetooth_facade.connect_device(device_address)


        has_device = False
        connected = False
        if self.bluetooth_facade.has_device(device_address):
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
                logging.error('test_connection_by_adapter: unexpected error')

        self.results = {'has_device': has_device, 'connected': connected}
        return all(self.results.values())


    @_test_retry_and_log
    def test_disconnection_by_adapter(self, device_address):
        """Test that the adapter of dut could disconnect the device successfully

        @param device_address: Address of the device.

        @returns: True if disconnection is performed. False otherwise.

        """
        return self.bluetooth_facade.disconnect_device(device_address)


    def _enter_command_mode(self, device):
        """Let the device enter command mode.

        Before using the device, need to call this method to make sure
        it is in the command mode.

        @param device: the bluetooth HID device

        @returns: True if successful. False otherwise.

        """
        result = _is_successful(_run_method(device.EnterCommandMode,
                                            'EnterCommandMode'))
        if not result:
            logging.error('EnterCommandMode failed')
        return result


    @_test_retry_and_log
    def test_connection_by_device(self, device):
        """Test that the device could connect to the adapter successfully.

        This emulates the behavior that a device may initiate a
        connection request after waking up from power saving mode.

        @param device: the bluetooth HID device

        @returns: True if connection is performed correctly by device and
                  the adapter also enters connection state.
                  False otherwise.

        """
        if not self._enter_command_mode(device):
            return False

        method_name = 'test_connection_by_device'
        connection_by_device = False
        adapter_address = self.bluetooth_hid_facade.address
        try:
            device.ConnectToRemoteAddress(adapter_address)
            connection_by_device = True
        except Exception as e:
            logging.error('%s (device): %s', method_name, e)
        except:
            logging.error('%s (device): unexpected error', method_name)

        connection_seen_by_adapter = False
        device_address = device.address
        device_is_connected = self.bluetooth_hid_facade.device_is_connected
        try:
            utils.poll_for_condition(
                    condition=lambda: device_is_connected(device_address),
                    timeout=self.ADAPTER_CONNECTION_TIMEOUT_SECS,
                    desc=('Waiting for connection from %s' % device_address))
            connection_seen_by_adapter = True
        except utils.TimeoutError as e:
            logging.error('%s (adapter): %s', method_name, e)
        except:
            logging.error('%s (adapter): unexpected error', method_name)

        self.results = {
                'connection_by_device': connection_by_device,
                'connection_seen_by_adapter': connection_seen_by_adapter}
        return all(self.results.values())


    @_test_retry_and_log
    def test_disconnection_by_device(self, device):
        """Test that the device could disconnect the adapter successfully.

        This emulates the behavior that a device may initiate a
        disconnection request before going into power saving mode.

        Note: should not try to enter command mode in this method. When
              a device is connected, there is no way to enter command mode.
              One could just issue a special disconnect command without
              entering command mode.

        @param device: the bluetooth HID device

        @returns: True if disconnection is performed correctly by device and
                  the adapter also observes the disconnection.
                  False otherwise.

        """
        method_name = 'test_disconnection_by_device'
        disconnection_by_device = False
        try:
            device.Disconnect()
            disconnection_by_device = True
        except Exception as e:
            logging.error('%s (device): %s', method_name, e)
        except:
            logging.error('%s (device): unexpected error', method_name)

        disconnection_seen_by_adapter = False
        device_address = device.address
        device_is_connected = self.bluetooth_hid_facade.device_is_connected
        try:
            utils.poll_for_condition(
                    condition=lambda: not device_is_connected(device_address),
                    timeout=self.ADAPTER_DISCONNECTION_TIMEOUT_SECS,
                    desc=('Waiting for disconnection from %s' % device_address))
            disconnection_seen_by_adapter = True
        except utils.TimeoutError as e:
            logging.error('%s (adapter): %s', method_name, e)
        except:
            logging.error('%s (adapter): unexpected error', method_name)

        self.results = {
                'disconnection_by_device': disconnection_by_device,
                'disconnection_seen_by_adapter': disconnection_seen_by_adapter}
        return all(self.results.values())


    def _get_device_name(self, device_address):
        """Get the device name.

        @returns: True if the device name is derived. None otherwise.

        """
        properties = self.bluetooth_facade.get_device_properties(
                device_address)
        self.discovered_device_name = properties.get('Name')
        return bool(self.discovered_device_name)


    @_test_retry_and_log
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


    @_test_retry_and_log
    def test_device_class_of_service(self, device_address,
                                     expected_class_of_service):
        """Test that the discovered device class of service is as expected.

        @param device_address: Address of the device.
        @param expected_class_of_service: the expected class of service

        @returns: True if the discovered class of service matches the
                  expected class of service. False otherwise.

        """
        properties = self.bluetooth_facade.get_device_properties(
                device_address)
        device_class = properties.get('Class')
        discovered_class_of_service = (device_class & self.CLASS_OF_SERVICE_MASK
                                       if device_class else None)

        self.results = {
                'device_class': device_class,
                'expected_class_of_service': expected_class_of_service,
                'discovered_class_of_service': discovered_class_of_service}
        return discovered_class_of_service == expected_class_of_service


    @_test_retry_and_log
    def test_device_class_of_device(self, device_address,
                                    expected_class_of_device):
        """Test that the discovered device class of device is as expected.

        @param device_address: Address of the device.
        @param expected_class_of_device: the expected class of device

        @returns: True if the discovered class of device matches the
                  expected class of device. False otherwise.

        """
        properties = self.bluetooth_facade.get_device_properties(
                device_address)
        device_class = properties.get('Class')
        discovered_class_of_device = (device_class & self.CLASS_OF_DEVICE_MASK
                                      if device_class else None)

        self.results = {
                'device_class': device_class,
                'expected_class_of_device': expected_class_of_device,
                'discovered_class_of_device': discovered_class_of_device}
        return discovered_class_of_device == expected_class_of_device


    def _get_btmon_log(self, method, *args, **kwargs):
        """Capture the btmon log when executing the specified method.

        @param method: the method to capture log.

        """
        self.bluetooth_le_facade.btmon_start()
        time.sleep(1)
        method(*args, **kwargs)
        time.sleep(1)
        self.bluetooth_le_facade.btmon_stop()


    def convert_to_adv_jiffies(self, adv_interval_ms):
        """Convert adv interval in ms to jiffies, i.e., multiples of 0.625 ms.

        @param adv_interval_ms: an advertising interval

        @returns: the equivalent jiffies

        """
        return adv_interval_ms / self.ADVERTISING_INTERVAL_UNIT

    def _verify_advertising_intervals(self, min_adv_interval_ms,
                                      max_adv_interval_ms):
        """Verify min and max advertising intervals.

        Advertising intervals look like
            Min advertising interval: 1280.000 msec (0x0800)
            Max advertising interval: 1280.000 msec (0x0800)

        @param min_adv_interval_ms: the min advertising interval
            in milli-second.
        @param max_adv_interval_ms: the max advertising interval
            in milli-second.

        @returns: a tuple of (True, True) if both min and max advertising
            intervals could be found. Otherwise, the corresponding element
            in the tuple if False.

        """
        min_str = ('Min advertising interval: %.3f msec (0x%04x)' %
                   (min_adv_interval_ms,
                    min_adv_interval_ms / self.ADVERTISING_INTERVAL_UNIT))
        logging.debug('min_adv_interval_ms: %s', min_str)
        min_adv_interval_ms_found = self.bluetooth_le_facade.btmon_find(min_str)

        max_str = ('Max advertising interval: %.3f msec (0x%04x)' %
                   (max_adv_interval_ms,
                    max_adv_interval_ms / self.ADVERTISING_INTERVAL_UNIT))
        logging.debug('max_adv_interval_ms: %s', max_str)
        max_adv_interval_ms_found = self.bluetooth_le_facade.btmon_find(max_str)

        return min_adv_interval_ms_found, max_adv_interval_ms_found


    @_test_retry_and_log(False)
    def test_register_advertisement(self, advertisement_data, instance_id,
                                    min_adv_interval_ms, max_adv_interval_ms):
        """Test that an advertisement could be registered correctly.

        This test verifies the following data:
        - advertisement added
        - manufactureri data
        - service UUIDs
        - service data
        - advertising intervals
        - advertising enabled

        @param advertisement_data: the data of an advertisement to register.
        @param instance_id: the instance id which starts at 1.
        @param min_adv_interval_ms: min_adv_interval in milli-second.
        @param max_adv_interval_ms: max_adv_interval in milli-second.

        @returns: True if the advertisement is registered correctly.
                  False otherwise.

        """
        self._get_btmon_log(self.bluetooth_le_facade.register_advertisement,
                            advertisement_data)

        # Verify that a new advertisement is added.
        advertisement_added = self.bluetooth_le_facade.btmon_find(
                'Advertising Added: %d' % instance_id)

        # Verify that the manufacturer data could be found.
        manufacturer_data = advertisement_data.get('ManufacturerData', '')
        for manufacturer_id in manufacturer_data:
            # The 'not assigned' text below means the manufacturer id
            # is not actually assigned to any real manufacturer.
            manufacturer_data_found = self.bluetooth_le_facade.btmon_find(
                    'Company: not assigned (%d)' % int(manufacturer_id, 16))

        # Verify that all service UUIDs could be found.
        service_uuids_found = True
        for uuid in advertisement_data.get('ServiceUUIDs', []):
            # Service UUIDs looks like ['0x180D', '0x180F']
            #   Heart Rate (0x180D)
            #   Battery Service (0x180F)
            if not self.bluetooth_le_facade.btmon_find('0x%s' % uuid):
                service_uuids_found = False
                break

        # Verify service data.
        service_data_found = True
        for uuid, data in advertisement_data.get('ServiceData', {}).items():
            # A service data looks like
            #   Service Data (UUID 0x9999): 0001020304
            # while uuid is '9999' and data is [0x00, 0x01, 0x02, 0x03, 0x04]
            data_str = ''.join(map(lambda n: '%02x' % n, data))
            if not self.bluetooth_le_facade.btmon_find(
                    'Service Data (UUID 0x%s): %s' % (uuid, data_str)):
                service_data_found = False
                break

        # Verify that the advertising intervals are correct.
        min_adv_interval_ms_found, max_adv_interval_ms_found = (
                self._verify_advertising_intervals(min_adv_interval_ms,
                                                   max_adv_interval_ms))

        # Verify advertising is enabled.
        advertising_enabled = self.bluetooth_le_facade.btmon_find(
                'Advertising: Enabled (0x01)')

        self.results = {
                'advertisement_added': advertisement_added,
                'manufacturer_data_found': manufacturer_data_found,
                'service_uuids_found': service_uuids_found,
                'service_data_found': service_data_found,
                'min_adv_interval_ms_found': min_adv_interval_ms_found,
                'max_adv_interval_ms_found': max_adv_interval_ms_found,
                'advertising_enabled': advertising_enabled,
        }
        return all(self.results.values())


    @_test_retry_and_log(False)
    def test_set_advertising_intervals(self, min_adv_interval_ms,
                                       max_adv_interval_ms):
        """Test that new advertising intervals could be set correctly.

        Note that setting advertising intervals does not enable/disable
        advertising. Hence, there is no need to check the advertising
        status.

        @param min_adv_interval_ms: the min advertising interval in ms.
        @param max_adv_interval_ms: the max advertising interval in ms.

        @returns: True if the new advertising intervals are correct.
                  False otherwise.

        """
        self._get_btmon_log(self.bluetooth_le_facade.set_advertising_intervals,
                            min_adv_interval_ms, max_adv_interval_ms)

        # Verify the new advertising intervals.
        # With intervals of 200 ms and 200 ms, the log looks like
        #   bluetoothd: Set Advertising Intervals: 0x0140, 0x0140
        txt = 'bluetoothd: Set Advertising Intervals: 0x%04x, 0x%04x'
        adv_intervals_found = self.bluetooth_le_facade.btmon_find(
                txt % (self.convert_to_adv_jiffies(min_adv_interval_ms),
                       self.convert_to_adv_jiffies(max_adv_interval_ms)))

        self.results = {'adv_intervals_found': adv_intervals_found}
        return all(self.results.values())


    @_test_retry_and_log(False)
    def test_reset_advertising(self, instance_ids):
        """Test that advertising is reset correctly.

        Note that reset advertising would set advertising intervals to
        the default values. However, we would not be able to observe
        the values change until new advertisements are registered.
        Therefore, it is required that a test_register_advertisement()
        test is conducted after this test.

        @param instance_ids: the list of instance IDs that should be removed.

        @returns: True if advertising is reset correctly.
                  False otherwise.

        """
        self._get_btmon_log(self.bluetooth_le_facade.reset_advertising)

        # Verify that every advertisement is removed. When an advertisement
        # with instance id 1 is removed, the log looks like
        #   @ Advertising Removed: 1
        txt = 'Advertising Removed: %d'
        for instance_id in instance_ids:
            if not self.bluetooth_le_facade.btmon_find(txt % instance_id):
                advertisement_removed = False
                logging.error('Failed to remove advertisement instance: %d',
                              instance_id)
                break
        else:
            advertisement_removed = True

        # Verify the advertising is disabled.
        advertising_disabled = self.bluetooth_le_facade.btmon_find(
                'Advertising: Disabled')

        self.results = {
                'advertisement_removed': advertisement_removed,
                'advertising_disabled': advertising_disabled,
        }
        return all(self.results.values())


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
        #       Otherwise, it would try to invoke bluetooth_mouse.__nonzero__()
        #       which just does not exist.
        for device_type in SUPPORTED_DEVICE_TYPES:
            if self.devices[device_type] is not None:
                self.devices[device_type].Close()
