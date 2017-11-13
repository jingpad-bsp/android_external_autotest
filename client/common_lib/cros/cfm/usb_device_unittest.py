import unittest

from autotest_lib.client.common_lib.cros.cfm import usb_device

class UsbDeviceTest(unittest.TestCase):
  """Unit tests for UsbDevice."""

  def setUp(self):
      self._usb_device = usb_device.UsbDevice(
          vid='vid',
          pid='pid',
          name='name',
          interfaces=['a', 'b'])

  def test_vendor_id(self):
      self.assertEqual(self._usb_device.vendor_id, 'vid')

  def test_product_id(self):
      self.assertEqual(self._usb_device.product_id, 'pid')

  def test_name(self):
      self.assertEqual(self._usb_device.name, 'name')

  def test_vid_pid(self):
      self.assertEqual(self._usb_device.vid_pid, 'vid:pid')

  def test_full_name(self):
      self.assertEqual(self._usb_device.full_name, 'name (vid:pid)')

  def test_usb_device(self):
      self.assertEqual(usb_device.UsbDevice.get_usb_device('vid:pid'),
                       self._usb_device)
      self.assertIsNone(usb_device.UsbDevice.get_usb_device(''))
