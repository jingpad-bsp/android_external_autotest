# -*- coding: utf-8 -*-
#
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This test looks in "/dev/video0" for a v4l2 video capture device,
# and starts streaming captured frames on the monitor.
# The observer then decides if the captured image looks good or defective,
# pressing enter key to let it pass or tab key to fail.
#
# Then the test will start to test the LED indicator located near the webcam.
# The LED test will be repeated for a fixed number (=5 at time of writing)
# of rounds, each round it will randomly decide whether to capture from the
# cam (the LED turns on when capturing). The captured image will NOT be
# shown on the monitor, so the observer must answer what he really sees.
# The test passes only if the answer for all rounds are correct.

import gtk
import glib
import pango
import numpy

from gtk import gdk
from random import randrange

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

import v4l2


DEVICE_NAME = '/dev/video0'
PREFERRED_WIDTH = 320
PREFERRED_HEIGHT = 240
PREFERRED_BUFFER_COUNT = 4

KEY_GOOD = gdk.keyval_from_name('Return')
KEY_BAD = gdk.keyval_from_name('Tab')

LABEL_FONT = pango.FontDescription('courier new condensed 16')

MESSAGE_STR = ('hit TAB to fail and ENTER to pass\n' +
               '錯誤請按 TAB，成功請按 ENTER\n')
MESSAGE_STR2 = ('hit TAB if the LED is off and ENTER if the LED is on\n' +
                '請檢查攝像頭 LED 指示燈, 沒亮請按 TAB, 燈亮請按 ENTER\n')


class factory_Camera(test.test):
    version = 1

    @staticmethod
    def get_best_frame_size(dev, pixel_format, width, height):
        '''Given the preferred frame size, find a reasonable frame size the
        capture device is capable of.

        currently it returns the smallest frame size that is equal or bigger
        than the preferred size in both axis. this does not conform to
        chrome browser's behavior, but is easier for testing purpose.
        '''
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
        if event.keyval == KEY_GOOD or event.keyval == KEY_BAD:
            if self.stage == 0:
                self.capture_stop()
                if event.keyval == KEY_BAD:
                    gtk.main_quit()
                self.img.hide()
                self.label.set_text(MESSAGE_STR2)
            else:
                if self.ledstats & 1:
                    self.capture_stop()
                if bool(self.ledstats & 1) != (event.keyval == KEY_GOOD):
                    self.ledfail = True
                self.ledstats >>= 1
            if self.stage == self.led_rounds:
                self.fail = False
                gtk.main_quit()
            self.stage += 1
            if self.ledstats & 1:
                self.capture_start()
            self.label.hide()
            glib.timeout_add(1000, lambda *x: self.label.show())
        return True

    def register_callbacks(self, w):
        w.connect('key-release-event', self.key_release_callback)
        w.add_events(gdk.KEY_RELEASE_MASK)

    def capture_start(self):
        self.dev.capture_mmap_start()
        self.gio_tag = glib.io_add_watch(self.dev.fd, glib.IO_IN,
            lambda *x:self.dev.capture_mmap_shot(self.render) or True,
            priority=glib.PRIORITY_LOW)

    def capture_stop(self):
        glib.source_remove(self.gio_tag)
        self.dev.capture_mmap_stop()

    def run_once(self,
                 led_rounds=1):
        '''Run the camera test

        Parameter
          led_rounds: 0 to disable the LED test,
                      1 to check if the LED turns on,
                      2 or higher to have multiple random turn on/off
                      (at least one on round and one off round is guranteed)
        '''
        factory.log('%s run_once' % self.__class__)

        self.fail = True
        self.ledfail = False
        self.led_rounds = led_rounds
        self.ledstats = 0
        if led_rounds == 1:
            # always on if only one round
            self.ledstats = 1
        elif led_rounds > 1:
            # ensure one on round and one off round
            self.ledstats = randrange(2 ** led_rounds - 2) + 1
        self.stage = 0

        self.label = label = gtk.Label(MESSAGE_STR)
        label.modify_font(LABEL_FONT)
        label.modify_fg(gtk.STATE_NORMAL, gdk.color_parse('light green'))

        test_widget = gtk.VBox()
        test_widget.modify_bg(gtk.STATE_NORMAL, gdk.color_parse('black'))
        test_widget.add(label)
        self.test_widget = test_widget

        self.img = None

        self.dev = dev = v4l2.Device(DEVICE_NAME)
        if not dev.cap.capabilities & v4l2.V4L2_CAP_VIDEO_CAPTURE:
            raise ValueError('%s does not support video capture interface'
                             % (DEVICE_NAME, ))
        if not dev.cap.capabilities & v4l2.V4L2_CAP_STREAMING:
            raise ValueError('%s does not support streaming I/O'
                             % (DEVICE_NAME, ))

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
        self.capture_start()

        ful.run_test_widget(self.job, test_widget,
            window_registration_callback=self.register_callbacks)

        # we don't call capture_mmap_stop here,
        # it will be called before returning from main loop.
        dev.capture_mmap_finish()

        if self.fail:
            raise error.TestFail('Camera test failed by user indication\n' \
                                 '品管人員懷疑攝影鏡頭故障，請檢修')
        if self.ledfail:
            raise error.TestFail('Camera LED test failed\n' \
                                 '攝影鏡頭 LED 測試不通過，請檢修')

        factory.log('%s run_once finished' % self.__class__)
