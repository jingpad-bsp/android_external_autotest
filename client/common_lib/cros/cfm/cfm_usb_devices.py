"""CfM USB device constants."""

from autotest_lib.client.common_lib.cros.cfm import usb_device

# Cameras
HUDDLY_GO = usb_device.UsbDevice(
    vid='2bd9',
    pid='0011',
    name='Huddly GO',
    interfaces=['uvcvideo', 'uvcvideo', 'uvcvideo', 'uvcvideo'],
)

LOGITECH_WEBCAM_C930E = usb_device.UsbDevice(
    vid='046d',
    pid='0843',
    name='Logitech Webcam C930e',
    interfaces=['uvcvideo', 'uvcvideo', 'snd-usb-audio', 'snd-usb-audio']
)

HD_PRO_WEBCAM_C920 = usb_device.UsbDevice(
    vid='046d',
    pid='082d',
    name='HD Pro Webcam C920',
    interfaces=['uvcvideo', 'uvcvideo', 'snd-usb-audio', 'snd-usb-audio'],
)

PTZ_PRO_CAMERA = usb_device.UsbDevice(
    vid='046d',
    pid='0853',
    name='PTZ Pro Camera',
    interfaces=['uvcvideo', 'uvcvideo','usbhid'],
)

# Speakers

ATRUS = usb_device.UsbDevice(
    vid='18d1',
    pid='8001',
    name='Hangouts Meet speakermic',
    interfaces=['snd-usb-audio', 'snd-usb-audio', 'snd-usb-audio', 'usbhid'],
)

JABRA_SPEAK_410 = usb_device.UsbDevice(
    vid='0b0e',
    pid='0412',
    name='Jabra SPEAK 410',
    interfaces=['snd-usb-audio', 'snd-usb-audio', 'snd-usb-audio'],
)

# MiMOs

# TODO(malmnas): double check if this is correct.
# Not listd in mimo_type_enum.proto
MIMO_VUE_HD = usb_device.UsbDevice(
    vid='17e9',
    pid='016b',
    name='MIMO VUE HD',
    interfaces=['udl'],
)

MIMO_VUE_HDMI = usb_device.UsbDevice(
    vid='266e',
    pid='0110',
    name='MIMO Vue HDMI (aka Plankton)',
    interfaces=['usbhid'],
)
