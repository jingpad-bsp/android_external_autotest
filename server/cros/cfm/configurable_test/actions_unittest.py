import mock
import unittest

from autotest_lib.client.common_lib.cros.cfm.usb import usb_device
from autotest_lib.client.common_lib.cros.cfm.usb import usb_device_spec
from autotest_lib.server.cros.cfm.configurable_test import actions
from autotest_lib.server.cros.cfm.configurable_test import action_context

# Test, disable missing-docstring
# pylint: disable=missing-docstring
class TestActions(unittest.TestCase):
    """
    Tests for the available actions for configurable CFM tests to run.
    """

    def setUp(self):
        self.host_mock = mock.MagicMock()
        self.cfm_facade_mock = mock.MagicMock()
        self.usb_device_collector_mock = mock.MagicMock()
        self.context_with_mocks = action_context.ActionContext(
                host=self.host_mock,
                cfm_facade=self.cfm_facade_mock,
                usb_device_collector=self.usb_device_collector_mock)


    def test_assert_file_does_not_contain_no_match(self):
        action = actions.AssertFileDoesNotContain('/foo', ['EE', 'WW'])
        context = action_context.ActionContext(
                file_contents_collector=FakeCollector('abc\ndef'))
        action.execute(context)

    def test_assert_file_does_not_contain_match(self):
        action = actions.AssertFileDoesNotContain('/foo', ['EE', 'WW'])
        context = action_context.ActionContext(
                file_contents_collector=FakeCollector('abc\naWWd'))
        self.assertRaises(AssertionError, lambda: action.execute(context))

    def test_assert_file_does_not_contain_regex_match(self):
        action = actions.AssertFileDoesNotContain('/foo', ['EE', 'W{3}Q+'])
        context = action_context.ActionContext(
                file_contents_collector=FakeCollector('abc\naWWWQQd'))
        self.assertRaises(AssertionError, lambda: action.execute(context))

    def test_reboot_dut_no_restart(self):
        action = actions.RebootDut()
        action.execute(self.context_with_mocks)
        self.host_mock.reboot.assert_called_once_with()
        self.assertFalse(self.cfm_facade_mock.method_calls)

    def test_reboot_dut_with_restart(self):
        action = actions.RebootDut(restart_chrome_for_cfm=True)
        action.execute(self.context_with_mocks)
        self.host_mock.reboot.assert_called_once_with()
        (self.cfm_facade_mock.restart_chrome_for_cfm
                .assert_called_once_with())
        (self.cfm_facade_mock.wait_for_meetings_telemetry_commands
                .assert_called_once_with())

    def test_assert_usb_device_collector(self):
        spec = usb_device_spec.UsbDeviceSpec(
                'vid', 'pid', 'product', ['iface'])
        action = actions.AssertUsbDevices(spec, lambda x: True)
        action.execute(self.context_with_mocks)

    def test_assert_usb_device_collector_matching_predicate(self):
        spec = usb_device_spec.UsbDeviceSpec(
                'vid', 'pid', 'product', ['iface'])
        device = usb_device.UsbDevice(
                'v', 'p', 'prod', ['if'])
        self.usb_device_collector_mock.get_devices_by_spec = mock.Mock(
                return_value=[device])
        action = actions.AssertUsbDevices(
                spec, lambda x: x[0].product_id == 'p')
        action.execute(self.context_with_mocks)

    def test_assert_usb_device_collector_non_matching_predicate(self):
        spec = usb_device_spec.UsbDeviceSpec(
                'vid', 'pid', 'product', ['iface'])
        device = usb_device.UsbDevice(
                'v', 'p', 'prod', ['if'])
        self.usb_device_collector_mock.get_devices_by_spec = mock.Mock(
                return_value=[device])
        action = actions.AssertUsbDevices(
                spec, lambda x: x[0].product_id == 'r')
        self.assertRaises(AssertionError, lambda: action.execute(
                self.context_with_mocks))

    def test_assert_usb_device_collector_default_predicate(self):
        spec = usb_device_spec.UsbDeviceSpec(
                'vid', 'pid', 'product', ['iface'])
        context = action_context.ActionContext(
                usb_device_collector=self.usb_device_collector_mock)
        self.usb_device_collector_mock.get_devices_by_spec = mock.Mock(
                return_value=[None])  # Default just checks list is of size 1
        action = actions.AssertUsbDevices(spec)
        action.execute(context)


class FakeCollector(object):
    def __init__(self, contents):
        self.contents = contents

    def collect_file_contents(self, path):
        return self.contents

