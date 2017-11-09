import unittest

from autotest_lib.client.common_lib.cros.cfm import cfm_usb_devices

class CfmUsbDevicesTest(unittest.TestCase):
  """Unit tests for cfm_usb_devices."""

  def test_get_cameras(self):
      self.assertEqual(cfm_usb_devices.CAMERAS, cfm_usb_devices.get_cameras())

  def test_get_camera(self):
      for c in cfm_usb_devices.CAMERAS:
          self.assertEqual(c, cfm_usb_devices.get_camera(c.vid_pid))

  def test_get_speakers(self):
      self.assertEqual(cfm_usb_devices.SPEAKERS, cfm_usb_devices.get_speakers())

  def test_get_camera(self):
      for s in cfm_usb_devices.SPEAKERS:
          self.assertEqual(s, cfm_usb_devices.get_speaker(s.vid_pid))
