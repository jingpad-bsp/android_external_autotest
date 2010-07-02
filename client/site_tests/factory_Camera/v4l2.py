# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import mmap
import copy
from errno import EINVAL as _EINVAL
import ctypes

import numpy

from v4l2_lowlevel import *

YUYV2RGB = numpy.array([
    [1.     ,  1.     , 1      , 0.     ,  0.     , 0.     ],
    [0.     , -0.39465, 2.03211, 0.     , -0.39465, 2.03211],
    [0.     ,  0.     , 0.     , 1.     ,  1.     , 1      ],
    [1.13983, -0.58060, 0.     , 1.13983, -0.58060, 0.     ]], dtype='f')
YUYV2RGB_shift = numpy.array([0., -128., 0., -128.], dtype="f")


class Device(object):
    def __init__(self, fn):
        self.fd = os.open(fn, os.O_RDONLY | os.O_NONBLOCK)
        self.cap = VIDIOC_QUERYCAP(self.fd)

    def __del__(self):
        os.close(self.fd)

    def enum_formats(self, typ):
        """Returns an iterable object which contains all formats supported
        by the v4l2 device for a certain stream (typ=V4L2_CAP_*).

        What it does is similar to the following C code:
        for (int i = 0; ; i++){
            arg.index = i;
            if (ioctl(....., &arg) == -1 && errno == EINVAL)
                return formats; // end of list
            formats.push_back(arg)
        }

        The difference is that we use generator instead storing all results
        in a list. This is more pythonic.
        """
        arg = v4l2_fmtdesc()
        arg.index = 0
        arg.type  = typ

        while True:
            try:
                VIDIOC_ENUM_FMT(self.fd, arg)
            except IOError as (errno, strerror):
                if errno == _EINVAL:
                    return
                raise
            yield arg.pixelformat, arg.description, arg.flags
            arg.index += 1

    def enum_framesizes(self, pixel_format):
        """Returns an iterable object which contains all frame size supported
        by the v4l2 device for a certain pixel format (=V4L2_PIX_FMT_*).

        Each entry in the list is a (int, int) or (xrange, xrange) tuple
        that represents possible discrete/continuous frame sizes.

        What it does is similar to the following C code:
        for (int i = 0; ; i++){
            arg.index = i;
            if (ioctl(....., &arg) == -1 && errno == EINVAL)
                return formats; // end of list
            formats.push_back(arg)
        }

        The difference is that we use generator instead storing all results
        in a list. This is more pythonic.
        """
        arg = v4l2_frmsizeenum()
        arg.index = 0
        arg.pixel_format = pixel_format

        while True:
            try:
                VIDIOC_ENUM_FRAMESIZES(self.fd, arg)
            except IOError as (errno, strerror):
                if errno == _EINVAL:
                    return
                raise
            if arg.type == V4L2_FRMSIZE_TYPE_DISCRETE:
                yield (arg.discrete.width, arg.discrete.height)
            if (arg.type == V4L2_FRMSIZE_TYPE_CONTINUOUS or
                arg.type == V4L2_FRMSIZE_TYPE_STEPWISE):
                yield (xrange(arg.stepwise.min_width,
                              arg.stepwise.max_width + 1,
                              arg.stepwise.step_width),
                       xrange(arg.stepwise.min_height,
                              arg.stepwise.max_height + 1,
                              arg.stepwise.step_height))
            arg.index += 1

    def capture_set_format(self, width, height, pixelformat, field):
        fmt = v4l2_format()
        fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
        fmt.fmt.pix.width = width
        fmt.fmt.pix.height = height
        fmt.fmt.pix.pixelformat = pixelformat
        fmt.fmt.pix.field = field
        r = VIDIOC_S_FMT(self.fd, fmt)
        self.capture_format = copy.deepcopy(fmt.fmt.pix)
        return r

    def capture_mmap_prepare(self, n_buffer=2, min_n_buffer=1):
        req = v4l2_requestbuffers()
        req.count = n_buffer
        req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
        req.memory = V4L2_MEMORY_MMAP
        VIDIOC_REQBUFS(self.fd, req)

        if req.count < min_n_buffer:
            raise Exception("insufficient capture buffer memory")

        self.mmapbuffers = []
        self.pixbuffers = []
        for i in xrange(req.count):
            buf = v4l2_buffer()
            buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
            buf.memory = V4L2_MEMORY_MMAP
            buf.index = i
            VIDIOC_QUERYBUF(self.fd, buf)

            m = mmap.mmap(
                self.fd, buf.length,
                prot=mmap.PROT_READ,
                flags=mmap.MAP_SHARED,
                offset=buf.m.offset)
            self.mmapbuffers.append(m)
            f = self.capture_format
            if f.pixelformat == V4L2_PIX_FMT_YUYV:
                p = numpy.ndarray((f.height, f.width / 2, 4),
                    dtype="u1", buffer=m, strides=(f.bytesperline, 4, 1))
            else:
                raise ValueError, "unknown pixel format"
            self.pixbuffers.append(p)

    def capture_mmap_start(self):
        for i in xrange(len(self.mmapbuffers)):
            req = v4l2_buffer()
            req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
            req.memory = V4L2_MEMORY_MMAP
            req.index = i
            VIDIOC_QBUF(self.fd, req)
        VIDIOC_STREAMON(self.fd, ctypes.c_int(V4L2_BUF_TYPE_VIDEO_CAPTURE))

    def capture_mmap_shot(self, callback=None):
        req = v4l2_buffer()
        req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
        req.memory = V4L2_MEMORY_MMAP
        VIDIOC_DQBUF(self.fd, req)
        if callback:
            f = self.capture_format
            if f.pixelformat == V4L2_PIX_FMT_YUYV:
                p = numpy.add(self.pixbuffers[req.index], YUYV2RGB_shift)
                p = numpy.dot(p, YUYV2RGB)
                p.shape = (f.height, f.width, 3)
            else:
                raise ValueError, "unknown pixel format"
            callback(p)
        VIDIOC_QBUF(self.fd, req)

    def capture_mmap_stop(self):
        VIDIOC_STREAMOFF(self.fd, ctypes.c_int(V4L2_BUF_TYPE_VIDEO_CAPTURE))

    def capture_mmap_finish(self):
        del self.pixbuffers
        for s in self.mmapbuffers:
            s.close()
        del self.mmapbuffers
        req = v4l2_requestbuffers()
        req.count = 0
        req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
        req.memory = V4L2_MEMORY_MMAP
        VIDIOC_REQBUFS(self.fd, req)
