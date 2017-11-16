# Copyright 2017 The Chromium OS Authors. All rights reserved.
# # Use of this source code is governed by a BSD-style license that can be
# # found in the LICENSE file.
#
# """extract data from output of use-devices on linux box"""
# The parser takes output of "usb-devices" as rawdata, and has capablities to
# 1. Populate usb data into dictionary
# 3. Extract defined peripheral devices based on CAMERA_MAP, SPEAKER_MAP.
# 4. As of now only one type touch panel is defined here, which is Mimo.
# 5. Check usb devices's interface.
# 6. Retrieve usb device based on product and manufacturer.

import cStringIO
import textfsm

from autotest_lib.client.common_lib.cros.cfm import cfm_usb_devices

USB_DEVICES_TPLT = (
    'Value Required Vendor ([0-9a-fA-F]+)\n'
    'Value Required ProdID ([0-9A-Fa-f]+)\n'
    'Value Required prev ([0-9a-fA-Z.]+)\n'
    'Value Manufacturer (.+)\n'
    'Value Product (.+)\n'
    'Value serialnumber ([0-9a-fA-Z\:\-]+)\n'
    'Value cinterfaces (\d)\n'
    'Value List intindex ([0-9])\n'
    'Value List intdriver ([A-Za-z-\(\)]+)\n\n'
    'Start\n'
         '  ^USB-Device -> Continue.Record\n'
         '  ^P:\s+Vendor=${Vendor}\s+ProdID=${ProdID}\sRev=${prev}\n'
         '  ^S:\s+Manufacturer=${Manufacturer}\n'
         '  ^S:\s+Product=${Product}\n'
         '  ^S:\s+SerialNumber=${serialnumber}\n'
         '  ^C:\s+\#Ifs=\s+${cinterfaces}\n'
         '  ^I:\s+If\#=\s+${intindex}.*Driver=${intdriver}\n'
)



def _extract_usb_data(rawdata):
    """populate usb data into list dictionary
    @param rawdata The output of "usb-devices" on CfM.
    @returns list of dictionary, examples:
    {'Manufacturer': 'USBest Technology', 'Product': 'SiS HID Touch Controller',
     'Vendor': '266e', 'intindex': ['0'], 'tport': '00', 'tcnt': '01',
     'serialnumber': '', 'tlev': '03', 'tdev': '18', 'dver': '',
     'intdriver': ['usbhid'], 'tbus': '01', 'prev': '03.00',
     'cinterfaces': '1', 'ProdID': '0110', 'tprnt': '14'}
    """
    usbdata = []
    rawdata += '\n'
    re_table = textfsm.TextFSM(cStringIO.StringIO(USB_DEVICES_TPLT))
    fsm_results = re_table.ParseText(rawdata)
    usbdata = [dict(zip(re_table.header, row)) for row in fsm_results]
    return usbdata


def _extract_peri_device(usbdata, vid_pids):
    """retrieve the list of dictionary for certain types of VID_PID
    @param usbdata  list of dictionary for usb devices
    @param vid_pids list of vid_pid combination
    @returns the list of dictionary for certain types of VID_PID
    """
    vid_pid_usb_list = []
    for vid_pid in vid_pids:
        vid_pid_usb_list.extend(_filter_by_vid_pid(usbdata, vid_pid))
    return vid_pid_usb_list


def _get_list_audio_device(usbdata):
    """retrieve the list of dictionary for all audio devices
    @param usbdata list of dictionary for usb devices
    @returns the list of dictionary for all audio devices
    """
    audio_device_list = []
    for _data in usbdata:
        if "snd-usb-audio" in _data['intdriver']:
            audio_device_list.append(_data)
    return audio_device_list


def _get_list_video_device(usbdata):
    """retrieve the list of dictionary for all video devices
    @param usbdata list of dictionary for usb devices
    @returns the list of dictionary for all video devices
    """
    video_device_list = []
    for _data in usbdata:
        if "uvcvideo" in _data['intdriver']:
            video_device_list.append(_data)
    return video_device_list


def _get_list_mimo_device(usbdata):
    """retrieve the list of dictionary for all touch panel devices
    @param usbdata list of dictionary for usb devices
    @returns the lists of dictionary
             one for displaylink, the other for touch controller
    """
    displaylink_list = []
    touchcontroller_list = []
    for _data in usbdata:
        if "udl" in _data['intdriver']:
            displaylink_list.append(_data)
        if "SiS HID Touch Controller" == _data['Product']:
            touchcontroller_list.append(_data)
    return displaylink_list, touchcontroller_list


def _get_list_by_product(usbdata, product_name):
    """retrieve the list of dictionary based on product_name
    @param usbdata list of dictionary for usb devices
    @returns the list of dictionary
    """
    usb_list_by_product = []
    for _data in usbdata:
        if product_name == _data['Product']:
            usb_list_by_product.append(_data)
    return usb_list_by_product


def _get_list_by_manufacturer(usbdata, manufacturer_name):
    """retrieve the list of dictionary based on manufacturer_name
    @param usbdata list of dictionary for usb devices
    @returns the list of dictionary
    """
    usb_list_by_manufacturer = []
    for _data in usbdata:
        if manufacturer_name == _data['Manufacturer']:
            usb_list_by_manufacturer.append(_data)
    return usb_list_by_manufacturer


def _get_vid_and_pid(vid_pid):
  """Parses out Vendor ID and Product ID from vid:pid string.

  @param vid_pid String on format vid:pid.
  @returns (vid,pid) tuple
  """
  assert ':' in vid_pid
  return vid_pid.split(':')


def _verify_usb_device_ok(usbdata, vid_pid):
    """
    Verifies that usb device has expected usb interfaces.

    @param usbdata list of dictionary for usb devices
    @param vid_pid VID, PID combination for the USB device to check.
    """
    device_found = False
    usb_device = cfm_usb_devices.get_usb_device(vid_pid)
    interface_set = set(usb_device.interfaces)
    length = len(interface_set)
    for _data in _filter_by_vid_pid(usbdata, vid_pid):
        device_found = True
        compare_set = set(_data['intdriver'][0:length])
        if compare_set != interface_set:
            raise RuntimeError(
                'Device %s has unexpected interfaces.' % vid_pid)
    if not device_found:
        raise RuntimeError('Expected at least one %s connected.' % vid_pid)


def _get_speakers(usbdata):
    """get number of speaker for each type
    @param usbdata  list of dictionary for usb devices
    @returns list of dictionary, key is VID_PID, value is number of speakers
    """
    number_speaker = {}
    for speaker in cfm_usb_devices.get_speakers():
        _number = len(_filter_by_vid_pid(usbdata, speaker.vid_pid))
        number_speaker[speaker.vid_pid] = _number
    return number_speaker


def _get_cameras(usbdata):
    """get number of camera for each type
    @param usbdata  list of dictionary for usb devices
    @returns list of dictionary, key is VID_PID, value is number of cameras
    """
    number_camera = {}
    for camera in cfm_usb_devices.get_cameras():
        _number = len(_filter_by_vid_pid(usbdata, camera.vid_pid))
        number_camera[camera.vid_pid] = _number
    return number_camera


def _get_display_mimo(usbdata):
    """get number of displaylink in Mimo for each type
    @param usbdata list of dictionary for usb devices
    @returns list of dictionary, key is VID_PID, value
              is number of displaylink
    """
    number_display = {}
    for _display in cfm_usb_devices.get_mimo_displays():
        _number = len(_filter_by_vid_pid(usbdata, _display.vid_pid))
        number_display[_display.vid_pid] = _number
    return number_display


def _get_controller_mimo(usbdata):
    """get number of touch controller Mimo for each type
    @param usbdata list of dictionary for usb devices
    @returns list of dictionary, key is VID_PID, value
             is number of touch controller
    """
    number_controller = {}
    for _controller in cfm_usb_devices.get_mimo_controllers():
        _number = len(_filter_by_vid_pid(usbdata, _controller.vid_pid))
        number_controller[_controller.vid_pid] = _number
    return number_controller


def _get_preferred_speaker(peripherals):
    """
    Get string for the 1st speakers in the device list

    @param peripheral dictionary for usb devices
    @returns name of preferred speaker
    """
    for vid_pid in peripherals:
      return next((s.full_name for s in cfm_usb_devices.get_speakers()
                   if s.vid_pid == vid_pid), None)


def _get_preferred_camera(peripherals):
    """
    Get string for the 1st camera in the device list

    @param peripheral dictionary for usb devices
    @returns name of preferred camera
    """
    for vid_pid in peripherals:
      return next((c.full_name for c in cfm_usb_devices.get_cameras()
                   if c.vid_pid == vid_pid), None)


def _get_device_prod(vid_pid):
    """
    Get product for vid_pid

    @param vid_pid vid and pid combo for device
    @returns product
    """
    device = next((s for s in cfm_usb_devices.get_speakers()
                   if s.vid_pid == vid_pid), None)
    if device:
      return device
    return next((c for c in cfm_usb_devices.get_cameras()
                 if c.vid_pid == vid_pid), None)


def _filter_by_vid_pid(usbdata, vid_pid):
  """
  Utility method for filter out items by vid and pid.

  @param usbdata list of dictionaries with usb device data
  @param vid_pid list of vid_pid combination
  @return list of dictionaries with usb devices with the
     the given vid and pid
  """
  vid, pid = _get_vid_and_pid(vid_pid)
  return [u for u in usbdata if
          vid == u['Vendor'] and pid == u['ProdID']]
