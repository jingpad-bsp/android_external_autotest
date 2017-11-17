"""CfM USB device constants.

This module contains constants for known USB device specs.

A UsbDeviceSpec instance represents a known USB device and its spec;
 - VendorID
 - ProdID
 - interfaces

This is different from a UsbDevice instance which represents a device actually
connected to the CfM and found by the usb-device command.

A UsbDevice instance found connected to a CfM is expected to match a known
UsbDeviceSpec (mapping is done using vid:pid), but due to bugs that might
not be the case (list of interfaces might be different for example).
"""

from autotest_lib.client.common_lib.cros.cfm import usb_device_spec

# Cameras
HUDDLY_GO = usb_device_spec.UsbDeviceSpec(
    vid='2bd9',
    pid='0011',
    product='Huddly GO',
    interfaces=['uvcvideo', 'uvcvideo', 'uvcvideo', 'uvcvideo'],
)

LOGITECH_WEBCAM_C930E = usb_device_spec.UsbDeviceSpec(
    vid='046d',
    pid='0843',
    product='Logitech Webcam C930e',
    interfaces=['uvcvideo', 'uvcvideo', 'snd-usb-audio', 'snd-usb-audio']
)

HD_PRO_WEBCAM_C920 = usb_device_spec.UsbDeviceSpec(
    vid='046d',
    pid='082d',
    product='HD Pro Webcam C920',
    interfaces=['uvcvideo', 'uvcvideo', 'snd-usb-audio', 'snd-usb-audio'],
)

PTZ_PRO_CAMERA = usb_device_spec.UsbDeviceSpec(
    vid='046d',
    pid='0853',
    product='PTZ Pro Camera',
    interfaces=['uvcvideo', 'uvcvideo','usbhid'],
)

CAMERAS = [
    HD_PRO_WEBCAM_C920,
    HUDDLY_GO,
    LOGITECH_WEBCAM_C930E,
    PTZ_PRO_CAMERA,
]

# Speakers

ATRUS = usb_device_spec.UsbDeviceSpec(
    vid='18d1',
    pid='8001',
    product='Hangouts Meet speakermic',
    interfaces=['snd-usb-audio', 'snd-usb-audio', 'snd-usb-audio', 'usbhid'],
)

JABRA_SPEAK_410 = usb_device_spec.UsbDeviceSpec(
    vid='0b0e',
    pid='0412',
    product='Jabra SPEAK 410',
    interfaces=['snd-usb-audio', 'snd-usb-audio', 'snd-usb-audio'],
)

SPEAKERS = [
    ATRUS,
    JABRA_SPEAK_410,
]

# MiMOs

# TODO(malmnas): double check if this is correct.
# Not listd in mimo_type_enum.proto
MIMO_VUE_HD = usb_device_spec.UsbDeviceSpec(
    vid='17e9',
    pid='016b',
    product='MIMO VUE HD',
    interfaces=['udl'],
)

MIMO_VUE_HDMI = usb_device_spec.UsbDeviceSpec(
    vid='266e',
    pid='0110',
    product='SiS HID Touch Controller',
    interfaces=['usbhid'],
)

# Utility methods

def get_cameras():
  """
  Returns the list of known CfM cameras.
  @return list of UsbDevices
  """
  return CAMERAS


def get_camera(vid_pid):
  """
  Return camera with the given vid_pid.
  @param vid_pid VendorId:ProductId
  @return UsbDevice with matching vid_pid or None if no match if found.
  """
  return next((c for c in CAMERAS if c.vid_pid == vid_pid), None)


def get_speakers():
  """
  Returns the list of known CfM speakers.
  @return list of UsbDevices
  """
  return SPEAKERS


def get_speaker(vid_pid):
  """
  Return speaker with the given vid_pid.
  @param vid_pid VendorId:ProductId
  @return UsbDevice with matching vid_pid or None if no match is found.
  """
  return next((s for s in SPEAKERS if s.vid_pid == vid_pid), None)


# TODO(malmnas): is this the right name?
def get_mimo_displays():
  """
  Return MiMO displays.
  @return list of UsbDevices.
  """
  return [MIMO_VUE_HD]


# TODO(malmnas): is this the right name?
def get_mimo_controllers():
  """
  Return MiMO controllers.
  @return list of UsbDevices.
  """
  return [MIMO_VUE_HDMI]


def get_usb_device_spec(vid_pid):
  """
  Look up UsbDeviceSpec based on vid_pid.
  @return UsbDeviceSpec with matching vid_pid or None if no match.
  """
  return usb_device_spec.UsbDeviceSpec.get_usb_device_spec(vid_pid)
