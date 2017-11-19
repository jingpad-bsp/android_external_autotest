import unittest

from autotest_lib.client.common_lib.cros import get_usb_devices
from autotest_lib.client.common_lib.cros.cfm import cfm_usb_devices

# pylint:disable=missing-docstring

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
    for speaker in cfm_usb_devices.get_speakers():
      self.assertEqual(
          get_usb_devices._get_device_prod(speaker.vid_pid), speaker)

    for camera in cfm_usb_devices.get_cameras():
      self.assertEquals(
          get_usb_devices._get_device_prod(camera.vid_pid), camera)

    self.assertIsNone(get_usb_devices._get_device_prod('invalid'))

  def test_get_vid_pid(self):
      vid, pid = get_usb_devices._get_vid_and_pid('123:456')
      self.assertEquals(vid, '123')
      self.assertEquals(pid, '456')

  def test_verify_usb_device_ok(self):
      usbdata = [
          {
              'Vendor': '18d1',
              'ProdID': '8001',
              'intdriver': ['snd-usb-audio', 'snd-usb-audio', 'snd-usb-audio',
                            'usbhid'],
          },
       ]
      vid_pid = '%s:%s' % (usbdata[0]['Vendor'], usbdata[0]['ProdID'])
      get_usb_devices._verify_usb_device_ok(usbdata, vid_pid)

      usbdata[0]['intdriver'] = []
      try:
        get_usb_devices._verify_usb_device_ok(usbdata, vid_pid)
        self.fail('Expected check to trigger RuntimeError')
      except RuntimeError:
        pass

if __name__ == "__main__":
    unittest.main()
