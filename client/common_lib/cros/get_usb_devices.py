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


# As of now there are certain types of cameras, speakers and touch-panel.
# New devices should be added to these global variables.
CAMERA_MAP = {'2bd9:0011': 'Huddly GO',
              '046d:0843': 'Logitech Webcam C930e',
              '046d:082d': 'HD Pro Webcam C920',
              '046d:0853': 'PTZ Pro Camera'}

SPEAKER_MAP = {'18d1:8001': 'Hangouts Meet speakermic',
               '0b0e:0412': 'Jabra SPEAK 410'}

TOUCH_DISPLAY_LIST = ['17e9:016b']
TOUCH_CONTROLLER_LIST = ['266e:0110']

INTERFACES_LIST = {'2bd9:0011':['uvcvideo', 'uvcvideo',
                                'uvcvideo', 'uvcvideo'],
                   '046d:0843':['uvcvideo', 'uvcvideo',
                                'snd-usb-audio', 'snd-usb-audio'],
                   '046d:082d':['uvcvideo', 'uvcvideo',
                                'snd-usb-audio', 'snd-usb-audio'],
                   '0b0e:0412':['snd-usb-audio', 'snd-usb-audio',
                                'snd-usb-audio'],
                   '18d1:8001':['snd-usb-audio', 'snd-usb-audio',
                                'snd-usb-audio', 'usbhid'],
                   '17e9:016b':['udl'],
                   '266e:0110':['usbhid'],
                   '046d:0853':['uvcvideo', 'uvcvideo','usbhid']
                  }


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


def _extract_peri_device(usbdata, vid_pid):
    """retrieve the list of dictionary for certain types of VID_PID
    @param usbdata  list of dictionary for usb devices
    @param vid_pid list of vid_pid combination
    @returns the list of dictionary for certain types of VID_PID
    """
    vid_pid_usb_list = []
    for _vid_pid in vid_pid:
        vid = _vid_pid.split(':')[0]
        pid = _vid_pid.split(':')[1]
        for _data in usbdata:
            if vid == _data['Vendor'] and pid ==  _data['ProdID']:
                vid_pid_usb_list.append(_data)
    return  vid_pid_usb_list


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


def _is_usb_device_ok(usbdata, vid_pid):
    """check usb device has expected usb interface
    @param usbdata list of dictionary for usb devices
    @vid_pid VID, PID combination for each type of USB device
    @returns
              int: number of device
              boolean: usb interfaces expected or not?
    """
    number_of_device = 0
    device_health = []
    vid, pid = _get_vid_and_pid(vid_pid)
    for _data in usbdata:
        if vid == _data['Vendor'] and pid == _data['ProdID']:
            number_of_device += 1
            compare_list = _data['intdriver'][0:len(INTERFACES_LIST[vid_pid])]
            if  cmp(compare_list, INTERFACES_LIST[vid_pid]) == 0:
                device_health.append('1')
            else:
                device_health.append('0')
    return number_of_device, device_health


def _get_speakers(usbdata):
    """get number of speaker for each type
    @param usbdata  list of dictionary for usb devices
    @returns list of dictionary, key is VID_PID, value is number of speakers
    """
    number_speaker = {}
    for _speaker in SPEAKER_MAP:
      vid, pid = _get_vid_and_pid(_speaker)
      _number = 0
      for _data in usbdata:
        if _data['Vendor'] == vid and _data['ProdID'] == pid:
          _number += 1
        number_speaker[_speaker] = _number
    return number_speaker


def _get_dual_speaker(usbdata):
    """check whether dual speakers are present
    @param usbdata  list of dictionary for usb devices
    @returns True or False
    """
    dual_speaker = None
    speaker_dict = _get_speakers(usbdata)
    for _key in speaker_dict:
        if speaker_dict[_key] == 2:
            dual_speaker = _key
            break
    return dual_speaker


def _get_cameras(usbdata):
    """get number of camera for each type
    @param usbdata  list of dictionary for usb devices
    @returns list of dictionary, key is VID_PID, value is number of cameras
    """
    number_camera = {}
    for _camera in CAMERA_MAP:
      vid, pid = _get_vid_and_pid(_camera)
      _number = 0
      for _data in usbdata:
        if _data['Vendor'] == vid and _data['ProdID'] == pid:
          _number += 1
      number_camera[_camera] = _number
    return number_camera

def _get_display_mimo(usbdata):
    """get number of displaylink in Mimo for each type
    @param usbdata list of dictionary for usb devices
    @returns list of dictionary, key is VID_PID, value
              is number of displaylink
    """
    number_display = {}
    for _display in TOUCH_DISPLAY_LIST:
      vid, pid = _get_vid_and_pid(_display)
      _number = 0
      for _data in usbdata:
        if _data['Vendor'] == vid and  _data['ProdID'] == pid:
          _number += 1
      number_display[_display] = _number
    return number_display

def _get_controller_mimo(usbdata):
    """get number of touch controller Mimo for each type
    @param usbdata list of dictionary for usb devices
    @returns list of dictionary, key is VID_PID, value
             is number of touch controller
    """
    number_controller = {}
    for _controller in TOUCH_CONTROLLER_LIST:
      vid, pid = _get_vid_and_pid(_controller)
      _number = 0
      for _data in usbdata:
        if _data['Vendor'] == vid and  _data['ProdID'] == pid:
          _number += 1
      number_controller[_controller] = _number
    return number_controller


def _get_preferred_speaker(peripheral):
    """get string for the 1st speakers in the device list
     @param peripheral dictionary for usb devices
     @returns name of preferred speaker
    """
    for _key in peripheral:
        if _key in SPEAKER_MAP:
          return '%s (%s)' % (SPEAKER_MAP[_key], _key)


def _get_preferred_camera(peripheral):
    """get string for the 1st camera in the device list
    @param peripheral dictionary for usb devices
    @returns name of preferred camera
    """
    for _key in peripheral:
        if _key in CAMERA_MAP:
            return '%s (%s)' % (CAMERA_MAP[_key], _key)


def _get_device_prod(vid_pid):
    """get product for vid_pid
    @param vid_pid vid and pid combo for device
    @returns product
    """
    if vid_pid in SPEAKER_MAP:
      return SPEAKER_MAP[vid_pid]
    if vid_pid in CAMERA_MAP:
      return CAMERA_MAP[vid_pid]
    return None
