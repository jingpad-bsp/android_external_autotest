import unittest

from autotest_lib.client.common_lib.cros import get_usb_devices


class GetDevicesTest(unittest.TestCase):
  """Unit test for file get_usb_devices."""

  def test_extract_usb_data_empty(self):
    self.assertEqual(get_usb_devices._extract_usb_data(""), [])

  def test_get_list_audio_device_empty(self):
    audio_device_list = get_usb_devices._get_list_audio_device([])
    self.assertEqual(audio_device_list, [])

  def test_get_list_audio_device_non_empty(self):
    usbdata = [
        {'intdriver': ['snd-usb-audio']},
        {'intdriver': ['uvcvideo']},
    ]
    audio_device_list = get_usb_devices._get_list_audio_device(usbdata)
    self.assertEqual(len(audio_device_list), 1)

  def test_get_device_prod(self):
    for pid_vid, value in get_usb_devices.SPEAKER_MAP.iteritems():
      self.assertEqual(get_usb_devices._get_device_prod(pid_vid), value)

    for pid_vid, value in get_usb_devices.CAMERA_MAP.iteritems():
      self.assertEquals(get_usb_devices._get_device_prod(pid_vid), value)

    self.assertIsNone(get_usb_devices._get_device_prod('invalid'))

  def test_get_vid_pid(self):
    vid, pid = get_usb_devices._get_vid_and_pid('123:456')
    self.assertEquals(vid, '123')
    self.assertEquals(pid, '456')


if __name__ == "__main__":
    unittest.main()
