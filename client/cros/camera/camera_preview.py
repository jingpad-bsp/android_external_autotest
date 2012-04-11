# -*- coding: utf-8 -*-
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Import guard for OpenCV.
try:
    import cv
    import cv2
except ImportError:
    # We can't raise error because it will fail the interpreter.
    pass

import gtk
import glib
import pango
import numpy

from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import ui as ful

# OpenCV will automatically search for a working camera device if we use the
# index -1.
DEFAULT_DEVICE_INDEX = -1

DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 480

PREFERRED_FPS = 30
PREFERRED_INTERVAL = int(round(1000.0 / PREFERRED_FPS))

GDK_PIXBUF_BIT_PER_SAMPLE = 8

LABEL_FONT = pango.FontDescription('courier new condensed 16')

class CameraPreview(object):
    '''Camera preview class.'''

    def __init__(
        self,
        msg,
        key_action_mapping,
        device_index=DEFAULT_DEVICE_INDEX,
        width=DEFAULT_WIDTH,
        height=DEFAULT_HEIGHT):
        '''Initializes and creates a preview widget.

        @param key_action_mapping: a dictionary to indicate function to invoke.
        @param device_index: an integer passed to OpenCV to detect video
                             capture device.
        @param width: the width of the preview image.
        @param height: the height of the preview image.
        @param msg: message to display on the preview widget.
        '''

        self.gio_tag = None
        self.key_action_mapping = key_action_mapping
        self.device_index = device_index

        # Blank images to fill the pixbuf when no device is detected.
        self.blankImg = numpy.zeros((height, width, 3), dtype=numpy.uint8)

        self.label = label = gtk.Label(msg)
        label.modify_font(LABEL_FONT)
        label.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse('light green'))

        self.widget = gtk.VBox()
        self.widget.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))
        self.widget.add(label)

        # Initialize the canvas.
        self.width = width
        self.height = height
        self.pixbuf = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False, 8,
            self.width, self.height)
        self.img = gtk.image_new_from_pixbuf(self.pixbuf)
        self.widget.add(self.img)
        self.img.show()

        self.widget.key_callback = self.key_release_callback

    def key_release_callback(self, widget, event):
        factory.log('key_release_callback %s(%s)' %
                    (event.keyval, gtk.gdk.keyval_name(event.keyval)))
        if event.keyval in self.key_action_mapping:
            if self.key_action_mapping[event.keyval] is not None:
                self.key_action_mapping[event.keyval]()
                return True

    def init_device(self, device_index):
        factory.log('Calling init_device with [%s]' % device_index)
        # Initialize the camera with OpenCV.
        self.dev = dev = cv2.VideoCapture(device_index)
        self.gio_tag = None
        if not dev.isOpened():
            self.dev.release()
            raise IOError(
                'Device #%s does not support video capture interface' %
                device_index)
        dev.set(cv.CV_CAP_PROP_FRAME_WIDTH, self.width)
        dev.set(cv.CV_CAP_PROP_FRAME_HEIGHT, self.height)
        self.capture_start()

    def capture_core(self):
        '''Captures an image and displays it.

        The FPS is determined by the camera hardware limit, the gtk display
        overhead and the amount of memory copy operations. This subroutine
        involves 3 copy operations of image data which usually takes less than
        10 ms on an average machine.
        '''
        # Read image from camera.
        ret, cvImg = self.dev.read()
        if not ret:
            raise IOError('Error while capturing. Camera disconnected?')

        # Convert from BGR to RGB in-place.
        cv2.cvtColor(cvImg, cv.CV_BGR2RGB, cvImg)

        # Convert to gdk pixbuf format.
        pbuf = gtk.gdk.pixbuf_new_from_data(cvImg.data,
            gtk.gdk.COLORSPACE_RGB, False, GDK_PIXBUF_BIT_PER_SAMPLE,
            cvImg.shape[1], cvImg.shape[0], cvImg.strides[0])

        # Copy to the display buffer.
        pbuf.copy_area(0, 0, pbuf.get_width(), pbuf.get_height(), self.pixbuf,
                       0, 0)

        # Queue for refreshing.
        self.img.queue_draw()

        return True

    def capture_start(self):
        # Register the image capturing subroutine using glib.
        # It will be called every PREFERRED_INTERVAL time.
        self.gio_tag = glib.timeout_add(PREFERRED_INTERVAL,
            lambda *x:self.capture_core(),
            priority=glib.PRIORITY_LOW)

    def capture_stop(self):
        # Unregister the image capturing subroutine.
        if self.gio_tag:
            glib.source_remove(self.gio_tag)
            self.dev.release()
            # reset pbuf to blank screen.
            pbuf = gtk.gdk.pixbuf_new_from_data(self.blankImg.data,
                gtk.gdk.COLORSPACE_RGB, False, GDK_PIXBUF_BIT_PER_SAMPLE,
                self.blankImg.shape[1],
                self.blankImg.shape[0],
                self.blankImg.strides[0])
            # Copy to the display buffer.
            pbuf.copy_area(0, 0, pbuf.get_width(), pbuf.get_height(),
                           self.pixbuf, 0, 0)
            # Queue for refreshing.
            self.img.queue_draw()
