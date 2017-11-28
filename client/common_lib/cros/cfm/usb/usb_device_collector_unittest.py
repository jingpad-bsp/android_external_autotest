import mock
import unittest

from autotest_lib.client.common_lib.cros.cfm.usb import usb_device_collector

# pylint: disable=missing-docstring

class UsbDeviceCollectorTest(unittest.TestCase):
    """Unit test for the class UsbDeviceCollector."""

    def test_get_usb_devices(self):
        usbdata = (
            'T:  Bus=01 Lev=01 Prnt=01 Port=01 Cnt=01 Dev#=  2 Spd=12  '
            'MxCh= 0\n'
            'D:  Ver= 2.00 Cls=00(>ifc ) Sub=00 Prot=00 MxPS=64 #Cfgs=  1\n'
            'P:  Vendor=0b0e ProdID=0412 Rev=01.09\n'
            'S:  Product=Jabra SPEAK 410 USB\n'
            'S:  SerialNumber=50C971FE192Bx010900\n'
            'C:  #Ifs= 4 Cfg#= 1 Atr=80 MxPwr=500mA\n'
            'I:  If#= 0 Alt= 0 #EPs= 0 Cls=01(audio) Sub=01 Prot=00 '
            'Driver=snd-usb-audio\n'
            'I:  If#= 1 Alt= 1 #EPs= 1 Cls=01(audio) Sub=02 Prot=00 '
            'Driver=snd-usb-audio\n'
            'I:  If#= 2 Alt= 0 #EPs= 0 Cls=01(audio) Sub=02 Prot=00 '
            'Driver=snd-usb-audio\n'
            'I:  If#= 3 Alt= 0 #EPs= 1 Cls=03(HID  ) Sub=00 Prot=00 '
            'Driver=usbfs')

        class FakeReturnValue(object):
            stdout = usbdata

        mock_host = mock.Mock()
        mock_host.run.return_value = FakeReturnValue()
        # Returned when stdout is called
        collector = usb_device_collector.UsbDeviceCollector(mock_host)
        devices = collector.get_usb_devices()
        self.assertEquals(1, len(devices))
        self.assertEquals('0b0e', devices[0].vendor_id)


if __name__ == "__main__":
    unittest.main()
