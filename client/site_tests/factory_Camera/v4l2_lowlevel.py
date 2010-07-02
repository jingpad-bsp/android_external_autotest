# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import ctypes

_ioctl = ctypes.CDLL("libc.so.6", use_errno = True).ioctl
_ioctl.restype = ctypes.c_int
_ioctl.argtypes = (ctypes.c_int,ctypes.c_int)

_IOC_NRBITS   = 8
_IOC_TYPEBITS = 8
_IOC_SIZEBITS = 14
_IOC_DIRBITS  = 2

_IOC_NRSHIFT   = 0
_IOC_TYPESHIFT = _IOC_NRSHIFT   + _IOC_NRBITS
_IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS
_IOC_DIRSHIFT  = _IOC_SIZESHIFT + _IOC_SIZEBITS

_IOC_NONE  = 0
_IOC_WRITE = 1
_IOC_READ  = 2

def _IOC(dir, type, nr, size):
    return ((dir << _IOC_DIRSHIFT) |
            (type << _IOC_TYPESHIFT) |
            (nr   << _IOC_NRSHIFT) |
            (size << _IOC_SIZESHIFT))

def _IO(type, nr):
    def ioctl(fd):
        if _ioctl(fd, _IOC(_IOC_NONE, ord(type), nr, 0)) == -1:
            raise IOError(ctypes.get_errno(), "ioctl error")
    return ioctl

def _IOR(type, nr, size):
    def ioctl(fd):
        arg = size()
        if _ioctl(fd, _IOC(_IOC_READ, ord(type), nr,
                  ctypes.sizeof(size)), ctypes.byref(arg)) == -1:
            raise IOError(ctypes.get_errno(), "ioctl error")
        return arg
    return ioctl

def _IOW(type, nr, size):
    def ioctl(fd, arg):
        if not isinstance(arg, size):
            raise TypeError()
        if _ioctl(fd, _IOC(_IOC_WRITE, ord(type), nr,
                  ctypes.sizeof(size)), ctypes.byref(arg)) == -1:
            raise IOError(ctypes.get_errno(), "ioctl error")
    return ioctl

def _IOWR(type, nr, size):
    def ioctl(fd, arg):
        if not isinstance(arg, size):
            raise TypeError()
        if _ioctl(fd, _IOC(_IOC_READ|_IOC_WRITE, ord(type), nr,
                  ctypes.sizeof(size)), ctypes.byref(arg)) == -1:
            raise IOError(ctypes.get_errno(), "ioctl error")
        return arg
    return ioctl

_kernel_time_t = ctypes.c_long
_kernel_suseconds_t = ctypes.c_long
class timeval(ctypes.Structure):
    _fields_ = [("tv_sec" , _kernel_time_t     ),
                ("tv_usec", _kernel_suseconds_t)]


V4L2_CAP_VIDEO_CAPTURE        = 0x00000001
V4L2_CAP_VIDEO_OUTPUT         = 0x00000002
V4L2_CAP_VIDEO_OVERLAY        = 0x00000004
V4L2_CAP_VBI_CAPTURE          = 0x00000010
V4L2_CAP_VBI_OUTPUT           = 0x00000020
V4L2_CAP_SLICED_VBI_CAPTURE   = 0x00000040
V4L2_CAP_SLICED_VBI_OUTPUT    = 0x00000080
V4L2_CAP_RDS_CAPTURE          = 0x00000100
V4L2_CAP_VIDEO_OUTPUT_OVERLAY = 0x00000200
V4L2_CAP_HW_FREQ_SEEK         = 0x00000400
V4L2_CAP_RDS_OUTPUT           = 0x00000800
V4L2_CAP_TUNER                = 0x00010000
V4L2_CAP_AUDIO                = 0x00020000
V4L2_CAP_RADIO                = 0x00040000
V4L2_CAP_MODULATOR            = 0x00080000
V4L2_CAP_READWRITE            = 0x01000000
V4L2_CAP_ASYNCIO              = 0x02000000
V4L2_CAP_STREAMING            = 0x04000000

V4L2_FMT_FLAG_COMPRESSED = 0x0001
V4L2_FMT_FLAG_EMULATED   = 0x0002

V4L2_FRMSIZE_TYPE_DISCRETE   = 1
V4L2_FRMSIZE_TYPE_CONTINUOUS = 2
V4L2_FRMSIZE_TYPE_STEPWISE   = 3

def v4l2_fourcc(a,b,c,d): return ord(a)|ord(b)<<8|ord(c)<<16|ord(d)<<24
V4L2_PIX_FMT_YUYV = v4l2_fourcc('Y', 'U', 'Y', 'V')

v4l2_buf_type = ctypes.c_int
V4L2_BUF_TYPE_VIDEO_CAPTURE        = 1
V4L2_BUF_TYPE_VIDEO_OUTPUT         = 2
V4L2_BUF_TYPE_VIDEO_OVERLAY        = 3
V4L2_BUF_TYPE_VBI_CAPTURE          = 4
V4L2_BUF_TYPE_VBI_OUTPUT           = 5
V4L2_BUF_TYPE_SLICED_VBI_CAPTURE   = 6
V4L2_BUF_TYPE_SLICED_VBI_OUTPUT    = 7
V4L2_BUF_TYPE_VIDEO_OUTPUT_OVERLAY = 8
V4L2_BUF_TYPE_PRIVATE              = 0x80

v4l2_memory = ctypes.c_int
V4L2_MEMORY_MMAP    = 1
V4L2_MEMORY_USERPTR = 2
V4L2_MEMORY_OVERLAY = 3

v4l2_field = ctypes.c_int
V4L2_FIELD_ANY           = 0
V4L2_FIELD_NONE          = 1
V4L2_FIELD_TOP           = 2
V4L2_FIELD_BOTTOM        = 3
V4L2_FIELD_INTERLACED    = 4
V4L2_FIELD_SEQ_TB        = 5
V4L2_FIELD_SEQ_BT        = 6
V4L2_FIELD_ALTERNATE     = 7
V4L2_FIELD_INTERLACED_TB = 8
V4L2_FIELD_INTERLACED_BT = 9

v4l2_colorspace = ctypes.c_int
V4L2_COLORSPACE_SMPTE170M     = 1
V4L2_COLORSPACE_SMPTE240M     = 2
V4L2_COLORSPACE_REC709        = 3
V4L2_COLORSPACE_BT878         = 4
V4L2_COLORSPACE_470_SYSTEM_M  = 5
V4L2_COLORSPACE_470_SYSTEM_BG = 6
V4L2_COLORSPACE_JPEG          = 7
V4L2_COLORSPACE_SRGB          = 8


class v4l2_capability(ctypes.Structure):
    _fields_ = [("driver"      , ctypes.c_char   * 16),
                ("card"        , ctypes.c_char   * 32),
                ("bus_info"    , ctypes.c_char   * 32),
                ("version"     , ctypes.c_uint32     ),
                ("capabilities", ctypes.c_uint32     ),
                ("reserved"    , ctypes.c_uint32 * 4 )]

class v4l2_timecode(ctypes.Structure):
    _fields_ = [("type"    , ctypes.c_uint32   ),
                ("flags"   , ctypes.c_uint32   ),
                ("frames"  , ctypes.c_uint8    ),
                ("seconds" , ctypes.c_uint8    ),
                ("minutes" , ctypes.c_uint8    ),
                ("hours"   , ctypes.c_uint8    ),
                ("userbits", ctypes.c_uint8 * 4)]

class v4l2_requestbuffers(ctypes.Structure):
    _fields_ = [("count"   , ctypes.c_uint32    ),
                ("type"    , v4l2_buf_type      ),
                ("memory"  , v4l2_memory        ),
                ("reserved", ctypes.c_uint32 * 2)]

class anonymous(ctypes.Union):
    _fields_ = [("offset" , ctypes.c_uint32),
                ("userptr", ctypes.c_ulong )]
class v4l2_buffer(ctypes.Structure):
    _fields_ = [("index"    , ctypes.c_uint32),
                ("type"     , v4l2_buf_type  ),
                ("bytesused", ctypes.c_uint32),
                ("flags"    , ctypes.c_uint32),
                ("field"    , v4l2_field     ),
                ("timestamp", timeval        ),
                ("timecode" , v4l2_timecode  ),
                ("sequence" , ctypes.c_uint32),
                ("memory"   , v4l2_memory    ),
                ("m"        , anonymous      ),
                ("length"   , ctypes.c_uint32),
                ("input"    , ctypes.c_uint32),
                ("reserved" , ctypes.c_uint32)]
del anonymous

class v4l2_fmtdesc(ctypes.Structure):
    _fields_ = [("index"      , ctypes.c_uint32    ),
                ("type"       , v4l2_buf_type      ),
                ("flags"      , ctypes.c_uint32    ),
                ("description", ctypes.c_char * 32 ),
                ("pixelformat", ctypes.c_uint32    ),
                ("reserved"   , ctypes.c_uint32 * 4)]

class v4l2_pix_format(ctypes.Structure):
    _fields_ = [("width"       , ctypes.c_uint32),
                ("height"      , ctypes.c_uint32),
                ("pixelformat" , ctypes.c_uint32),
                ("field"       , v4l2_field     ),
                ("bytesperline", ctypes.c_uint32),
                ("sizeimage"   , ctypes.c_uint32),
                ("colorspace"  , v4l2_colorspace),
                ("priv"        , ctypes.c_uint32)]

# **** FIXME!!! ****
v4l2_window = v4l2_vbi_format = v4l2_sliced_vbi_format = ctypes.c_void_p
# ******************

class anonymous(ctypes.Union):
    _fields_ = [("pix"     , v4l2_pix_format       ),
                ("win"     , v4l2_window           ),
                ("vbi"     , v4l2_vbi_format       ),
                ("sliced"  , v4l2_sliced_vbi_format),
                ("raw_data", ctypes.c_ubyte * 200  )]
class v4l2_format(ctypes.Structure):
    _fields_ = [("type", v4l2_buf_type),
                ("fmt" , anonymous    )]
del anonymous

class v4l2_frmsize_discrete(ctypes.Structure):
    _fields_ = [("width" , ctypes.c_uint32),
                ("height", ctypes.c_uint32)]

class v4l2_frmsize_stepwise(ctypes.Structure):
    _fields_ = [("min_width"  , ctypes.c_uint32),
                ("max_width"  , ctypes.c_uint32),
                ("step_width" , ctypes.c_uint32),
                ("min_height" , ctypes.c_uint32),
                ("max_height" , ctypes.c_uint32),
                ("step_height", ctypes.c_uint32)]

class anonymous(ctypes.Union):
    _fields_ = [("discrete", v4l2_frmsize_discrete),
                ("stepwise", v4l2_frmsize_stepwise)]
class v4l2_frmsizeenum(ctypes.Structure):
    _anonymous_ = ["anonymous"]
    _fields_ = [("index"       , ctypes.c_uint32    ),
                ("pixel_format", ctypes.c_uint32    ),
                ("type"        , ctypes.c_uint32    ),
                ("anonymous"   , anonymous          ),
                ("reserved"    , ctypes.c_uint32 * 2)]
del anonymous

VIDIOC_QUERYCAP            = _IOR ('V', 0 , v4l2_capability)
VIDIOC_RESERVED            = _IO  ('V', 1 )
VIDIOC_ENUM_FMT            = _IOWR('V', 2 , v4l2_fmtdesc)
VIDIOC_G_FMT               = _IOWR('V', 4 , v4l2_format)
VIDIOC_S_FMT               = _IOWR('V', 5 , v4l2_format)
VIDIOC_REQBUFS             = _IOWR('V', 8 , v4l2_requestbuffers)
VIDIOC_QUERYBUF            = _IOWR('V', 9 , v4l2_buffer)
#VIDIOC_G_FBUF              = _IOR ('V', 10, v4l2_framebuffer)
#VIDIOC_S_FBUF              = _IOW ('V', 11, v4l2_framebuffer)
#VIDIOC_OVERLAY             = _IOW ('V', 14, ctypes.c_int)
VIDIOC_QBUF                = _IOWR('V', 15, v4l2_buffer)
VIDIOC_DQBUF               = _IOWR('V', 17, v4l2_buffer)
VIDIOC_STREAMON            = _IOW ('V', 18, ctypes.c_int)
VIDIOC_STREAMOFF           = _IOW ('V', 19, ctypes.c_int)
#VIDIOC_G_PARM              = _IOWR('V', 21, v4l2_streamparm)
#VIDIOC_S_PARM              = _IOWR('V', 22, v4l2_streamparm)
#VIDIOC_G_STD               = _IOR ('V', 23, v4l2_std_id)
#VIDIOC_S_STD               = _IOW ('V', 24, v4l2_std_id)
#VIDIOC_ENUMSTD             = _IOWR('V', 25, v4l2_standard)
#VIDIOC_ENUMINPUT           = _IOWR('V', 26, v4l2_input)
#VIDIOC_G_CTRL              = _IOWR('V', 27, v4l2_control)
#VIDIOC_S_CTRL              = _IOWR('V', 28, v4l2_control)
#VIDIOC_G_TUNER             = _IOWR('V', 29, v4l2_tuner)
#VIDIOC_S_TUNER             = _IOW ('V', 30, v4l2_tuner)
#VIDIOC_G_AUDIO             = _IOR ('V', 33, v4l2_audio)
#VIDIOC_S_AUDIO             = _IOW ('V', 34, v4l2_audio)
#VIDIOC_QUERYCTRL           = _IOWR('V', 36, v4l2_queryctrl)
#VIDIOC_QUERYMENU           = _IOWR('V', 37, v4l2_querymenu)
#VIDIOC_G_INPUT             = _IOR ('V', 38, ctypes.c_int)
#VIDIOC_S_INPUT             = _IOWR('V', 39, ctypes.c_int)
#VIDIOC_G_OUTPUT            = _IOR ('V', 46, ctypes.c_int)
#VIDIOC_S_OUTPUT            = _IOWR('V', 47, ctypes.c_int)
#VIDIOC_ENUMOUTPUT          = _IOWR('V', 48, v4l2_output)
#VIDIOC_G_AUDOUT            = _IOR ('V', 49, v4l2_audioout)
#VIDIOC_S_AUDOUT            = _IOW ('V', 50, v4l2_audioout)
#VIDIOC_G_MODULATOR         = _IOWR('V', 54, v4l2_modulator)
#VIDIOC_S_MODULATOR         = _IOW ('V', 55, v4l2_modulator)
#VIDIOC_G_FREQUENCY         = _IOWR('V', 56, v4l2_frequency)
#VIDIOC_S_FREQUENCY         = _IOW ('V', 57, v4l2_frequency)
#VIDIOC_CROPCAP             = _IOWR('V', 58, v4l2_cropcap)
#VIDIOC_G_CROP              = _IOWR('V', 59, v4l2_crop)
#VIDIOC_S_CROP              = _IOW ('V', 60, v4l2_crop)
#VIDIOC_G_JPEGCOMP          = _IOR ('V', 61, v4l2_jpegcompression)
#VIDIOC_S_JPEGCOMP          = _IOW ('V', 62, v4l2_jpegcompression)
#VIDIOC_QUERYSTD            = _IOR ('V', 63, v4l2_std_id)
#VIDIOC_TRY_FMT             = _IOWR('V', 64, v4l2_format)
#VIDIOC_ENUMAUDIO           = _IOWR('V', 65, v4l2_audio)
#VIDIOC_ENUMAUDOUT          = _IOWR('V', 66, v4l2_audioout)
#VIDIOC_G_PRIORITY          = _IOR ('V', 67, v4l2_priority)
#VIDIOC_S_PRIORITY          = _IOW ('V', 68, v4l2_priority)
#VIDIOC_G_SLICED_VBI_CAP    = _IOWR('V', 69, v4l2_sliced_vbi_cap)
#VIDIOC_LOG_STATUS          = _IO  ('V', 70)
#VIDIOC_G_EXT_CTRLS         = _IOWR('V', 71, v4l2_ext_controls)
#VIDIOC_S_EXT_CTRLS         = _IOWR('V', 72, v4l2_ext_controls)
#VIDIOC_TRY_EXT_CTRLS       = _IOWR('V', 73, v4l2_ext_controls)
VIDIOC_ENUM_FRAMESIZES     = _IOWR('V', 74, v4l2_frmsizeenum)
#VIDIOC_ENUM_FRAMEINTERVALS = _IOWR('V', 75, v4l2_frmivalenum)
#VIDIOC_G_ENC_INDEX         = _IOR ('V', 76, v4l2_enc_idx)
#VIDIOC_ENCODER_CMD         = _IOWR('V', 77, v4l2_encoder_cmd)
#VIDIOC_TRY_ENCODER_CMD     = _IOWR('V', 78, v4l2_encoder_cmd)
