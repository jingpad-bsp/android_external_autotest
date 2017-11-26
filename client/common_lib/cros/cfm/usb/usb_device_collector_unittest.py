import mock
import unittest

from autotest_lib.client.common_lib.cros.cfm.usb import usb_device_collector
from autotest_lib.client.common_lib.cros.cfm.usb import usb_device


class UsbDeviceCollectorTest(unittest.TestCase):
    """Unit test for the class UsbDeviceCollector."""

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

        mock_host = mock.Mock()
        mock_host.run.return_value = usbdata
        collector = usb_device_collector.UsbDeviceCollector(mock_host)
        collector.verify_usb_device_interfaces_ok(device)


if __name__ == "__main__":
    unittest.main()
