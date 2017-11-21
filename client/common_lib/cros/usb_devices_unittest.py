
import unittest

from autotest_lib.client.common_lib.cros import usb_devices
from autotest_lib.client.common_lib.cros.cfm import usb_device


class MockUsbDataCollector(object):
    """Mock UsbDataCollector used for unit tests."""

    def __init__(self, usbdata):
        """
        Constructor.
        """
        self.usbdata = usbdata

    def collect(self):
        """Collect USB data from DUT."""
        return self.usbdata


class UsbDevicesTest(unittest.TestCase):
    """Unit test for the class UsbDevices."""

    def test_verify_usb_device_interfaces_ok_pass(self):
        """Unit test for verify_usb_device_interfaces_ok."""
        vid_pid = '17e9:016b'
        usbdata = [
            {
                'Vendor': '17e9',
                'ProdID': '016b',
                'intdriver': ['udl']
            },
        ]
        device = usb_device.UsbDevice(
            vid=usbdata[0]['Vendor'],
            pid=usbdata[0]['ProdID'],
            product='dummy',
            interfaces=usbdata[0]['intdriver'])
        mgr = usb_devices.UsbDevices(MockUsbDataCollector(usbdata))
        mgr.verify_usb_device_interfaces_ok(device)

    def test_verify_usb_device_interfaces_ok_fail(self):
        """Unit test for verify_usb_device_interfaces_ok."""
        vid_pid = '17e9:016b'
        usbdata = [
            {
                'Vendor': '17e9',
                'ProdID': '016b',
                'intdriver': []
            },
        ]
        device = usb_device.UsbDevice(
            vid=usbdata[0]['Vendor'],
            pid=usbdata[0]['ProdID'],
            product='dummy',
            interfaces=usbdata[0]['intdriver'])
        mgr = usb_devices.UsbDevices(MockUsbDataCollector(usbdata))
        with self.assertRaises(RuntimeError):
            mgr.verify_usb_device_interfaces_ok(device)


if __name__ == "__main__":
    unittest.main()
