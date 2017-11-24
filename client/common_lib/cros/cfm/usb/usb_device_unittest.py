import unittest

from autotest_lib.client.common_lib.cros.cfm.usb import usb_device

# pylint: disable=missing-docstring

class UsbDeviceTest(unittest.TestCase):
  """Unit tests for UsbDevice."""

  def setUp(self):
      self._usb_device = usb_device.UsbDevice(
          vid='vid',
          pid='pid',
          product='product',
          interfaces=['a', 'b'])

  def test_vendor_id(self):
      self.assertEqual(self._usb_device.vendor_id, 'vid')

  def test_product_id(self):
      self.assertEqual(self._usb_device.product_id, 'pid')

  def test_product(self):
      self.assertEqual(self._usb_device.product, 'product')

  def test_vid_pid(self):
      self.assertEqual(self._usb_device.vid_pid, 'vid:pid')
