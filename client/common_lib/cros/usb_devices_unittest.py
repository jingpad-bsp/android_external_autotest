
import unittest

from autotest_lib.client.common_lib.cros import usb_devices
from autotest_lib.client.common_lib.cros.cfm import cfm_usb_devices


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

    def test_get_camera_counts(self):
        """Unit test for get_camera_counts."""
        usbdata = [
            {
                'Vendor': cfm_usb_devices.HUDDLY_GO.vendor_id,
                'ProdID': cfm_usb_devices.HUDDLY_GO.product_id
            }
        ]
        devices = usb_devices.UsbDevices(MockUsbDataCollector(usbdata))

        camera_counts = devices.get_camera_counts()
        for camera in cfm_usb_devices.get_cameras():
            if camera == cfm_usb_devices.HUDDLY_GO:
                self.assertEquals(1, camera_counts.get(camera.vid_pid))
            else:
                self.assertEquals(0, camera_counts.get(camera.vid_pid))

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
        devices = usb_devices.UsbDevices(MockUsbDataCollector(usbdata))
        devices.verify_usb_device_interfaces_ok(vid_pid)

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

        devices = usb_devices.UsbDevices(MockUsbDataCollector(usbdata))
        try:
            devices.verify_usb_device_interfaces_ok(vid_pid)
            self.fail('Expected check to trigger RuntimeError')
        except RuntimeError:
            pass


if __name__ == "__main__":
    unittest.main()
