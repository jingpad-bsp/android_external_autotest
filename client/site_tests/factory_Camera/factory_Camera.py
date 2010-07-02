# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This test looks in "/dev/video0" for a v4l2 video capture device,
# and starts streaming captured frames on the monitor.
# The observer then decides if the captured image looks good or defective,
# pressing enter key to let it pass or tab key to fail.


import gtk
from gtk import gdk
import glib
import pango
import numpy

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

import v4l2


DEVICE_NAME = "/dev/video0"
PREFERRED_WIDTH = 320
PREFERRED_HEIGHT = 240
PREFERRED_BUFFER_COUNT = 4


class factory_Camera(test.test):
    version = 1
    key_good = gdk.keyval_from_name('Return')
    key_bad = gdk.keyval_from_name('Tab')

    @staticmethod
    def get_best_frame_size(dev, pixel_format, width, height):
        """Given the preferred frame size, find a reasonable frame size the
        capture device is capable of.

        currently it returns the smallest frame size that is equal or bigger
        than the preferred size in both axis. this does not conform to
        chrome browser's behavior, but is easier for testing purpose.
        """
        sizes = [(w, h) for w, h in dev.enum_framesizes(pixel_format)
                 if type(w) is int or type(w) is long]
        if not sizes:
            return (width, height)
        if False: # see doc string above
            for w, h in sizes:
                if w >= width and h >= height:
                    return (w,h)
        good_sizes = [(w, h) for w, h in sizes if w >= width and h >= height]
        if good_sizes:
            return min(good_sizes, key=lambda x: x[0] * x[1])
        return max(sizes, key=lambda x: x[0] * x[1])

    def render(self, pixels):
        numpy.maximum(pixels, 0, pixels)
        numpy.minimum(pixels, 255, pixels)
        self.pixels[:] = pixels
        self.img.queue_draw()

    def key_release_callback(self, widget, event):
        factory.log('key_release_callback %s(%s)' %
                    (event.keyval, gdk.keyval_name(event.keyval)))
        if event.keyval == self.key_good:
            self.fail = False
            gtk.main_quit()
        if event.keyval == self.key_bad:
            gtk.main_quit()
        self.ft_state.exit_on_trigger(event)
        return

    def register_callbacks(self, w):
        w.connect('key-release-event', self.key_release_callback)
        w.add_events(gdk.KEY_RELEASE_MASK)

    def run_once(self, test_widget_size=None, trigger_set=None,
                 result_file_path=None):

        factory.log('%s run_once' % self.__class__)

        self.fail = True

        self.ft_state = ful.State(
            trigger_set=trigger_set,
            result_file_path=result_file_path)

        label = gtk.Label(
            "Press %s key if the image looks good\nPress %s otherwise"
            % (gdk.keyval_name(self.key_good),gdk.keyval_name(self.key_bad)))

        label.modify_font(pango.FontDescription('courier new condensed 12'))
        label.modify_fg(gtk.STATE_NORMAL, gdk.color_parse('light green'))

        test_widget = gtk.VBox()
        test_widget.modify_bg(gtk.STATE_NORMAL, gdk.color_parse('black'))
        test_widget.add(label)
        self.test_widget = test_widget

        self.img = None

        dev = v4l2.Device(DEVICE_NAME)
        if not dev.cap.capabilities & v4l2.V4L2_CAP_VIDEO_CAPTURE:
            raise ValueError("%s doesn't support video capture interface"
                             % (DEVICE_NAME, ))
        if not dev.cap.capabilities & v4l2.V4L2_CAP_STREAMING:
            raise ValueError("%s doesn't support streaming I/O"
                             % (DEVICE_NAME, ))
        glib.io_add_watch(dev.fd, glib.IO_IN,
            lambda *x:dev.capture_mmap_shot(self.render) or True,
            priority=glib.PRIORITY_LOW)

        frame_size = self.get_best_frame_size(dev, v4l2.V4L2_PIX_FMT_YUYV,
            PREFERRED_WIDTH, PREFERRED_HEIGHT)

        adj_fmt = dev.capture_set_format(frame_size[0], frame_size[1],
            v4l2.V4L2_PIX_FMT_YUYV, v4l2.V4L2_FIELD_INTERLACED)
        width, height = adj_fmt.fmt.pix.width, adj_fmt.fmt.pix.height

        self.pixbuf = gdk.Pixbuf(gdk.COLORSPACE_RGB, False, 8,
            width, height)
        self.pixels = self.pixbuf.get_pixels_array()
        self.img = gtk.image_new_from_pixbuf(self.pixbuf)
        self.test_widget.add(self.img)
        self.img.show()

        dev.capture_mmap_prepare(PREFERRED_BUFFER_COUNT, 2)
        dev.capture_mmap_start()

        self.ft_state.run_test_widget(
            test_widget=test_widget,
            test_widget_size=test_widget_size,
            window_registration_callback=self.register_callbacks)

        dev.capture_mmap_stop()
        dev.capture_mmap_finish()

        if self.fail:
            raise error.TestFail('camera test failed by user indication')

        factory.log('%s run_once finished' % self.__class__)
