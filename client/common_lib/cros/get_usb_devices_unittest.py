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


if __name__ == "__main__":
    unittest.main()
