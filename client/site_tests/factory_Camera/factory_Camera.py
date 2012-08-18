# -*- coding: utf-8 -*-
#
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This test searches for a v4l2 video capture device, and starts streaming
# captured frames on the monitor.
# The observer then decides if the captured image looks good or defective,
# pressing enter key to let it pass or tab key to fail.
#
# Then the test will start to test the LED indicator located near the webcam.
# The LED test will be repeated for a fixed number (=5 at time of writing)
# of rounds, each round it will randomly decide whether to capture from the
# cam (the LED turns on when capturing). The captured image will NOT be
# shown on the monitor, so the observer must answer what he really sees.
# The test passes only if the answer for all rounds are correct.


# The current configuration of buildbot will try to compile Python
# files for the remote test purpose. Since this is done on the host,
# it can't use any library that is not installed there even if the
# library might be available on the target. We currently do not have
# OpenCV on the host so we have to try-catch the import in order to
# avoid the compilation error.
#
# TODO: Fix it either when we have OpenCV on the host or the build
#       configuration for Python files in the autotest changes.

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
import time
import os

from gtk import gdk
from random import randrange

from autotest_lib.client.cros import factory_setup_modules
from cros.factory.test import factory
from cros.factory.test import ui as ful
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

# OpenCV will automatically search for a working camera device if we use the
# index -1.
DEVICE_INDEX = -1

PREFERRED_FPS = 30
PREFERRED_INTERVAL = int(round(1000.0 / PREFERRED_FPS))
FPS_UPDATE_FACTOR = 0.1

GDK_PIXBUF_BIT_PER_SAMPLE = 8

KEY_GOOD = gdk.keyval_from_name('Return')
KEY_BAD = gdk.keyval_from_name('Tab')

LABEL_FONT = pango.FontDescription('courier new condensed 16')

MESSAGE_STR = ('hit TAB to fail and ENTER to pass\n' +
               '错误请按 TAB，成功请按 ENTER\n')
MESSAGE_STR2 = ('hit TAB if the LED is off and ENTER if the LED is on\n' +
                '请检查摄像头 LED 指示灯, 没亮请按 TAB, 灯亮请按 ENTER\n')


class factory_Camera(test.test):
    version = 1

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

    def capture_core(self):
        '''Captures an image and displays it

        The FPS is determined by the camera hardware limit, the gtk display
        overhead and the amount of memory copy operations. This subroutine
        involves 3 copy operations of image data which usually takes less than
        10 ms on an average machine.
        '''
        # Read image from camera.
        ret, cvImg = self.dev.read()
        if not ret:
            raise IOError("Error while capturing. Camera disconnected?")

        # Convert from BGR to RGB in-place.
        cv2.cvtColor(cvImg, cv.CV_BGR2RGB, cvImg)

        # Convert to gdk pixbuf format.
        pbuf = gdk.pixbuf_new_from_data(cvImg.data,
            gdk.COLORSPACE_RGB, False, GDK_PIXBUF_BIT_PER_SAMPLE,
            cvImg.shape[1], cvImg.shape[0], cvImg.strides[0])

        # Copy to the display buffer.
        pbuf.copy_area(0, 0, pbuf.get_width(), pbuf.get_height(), self.pixbuf,
                       0, 0)

        # Queue for refreshing.
        self.img.queue_draw()

        # Update FPS if required.
        if self.show_fps:
            current_time = time.clock()
            self.current_fps = (self.current_fps * (1 - FPS_UPDATE_FACTOR) +
                                1.0 / (current_time - self.last_capture_time) *
                                FPS_UPDATE_FACTOR)
            self.last_capture_time = current_time

            self.label.set_text(MESSAGE_STR2 +
                                'FPS = ' + '%.2f\n' % self.current_fps)

        return True

    def register_callbacks(self, w):
        w.connect('key-release-event', self.key_release_callback)
        w.add_events(gdk.KEY_RELEASE_MASK)

    def capture_start(self):
        # Register the image capturing subroutine using glib.
        # It will be called every PREFERRED_INTERVAL time.
        self.gio_tag = glib.timeout_add( PREFERRED_INTERVAL,
            lambda *x:self.capture_core(),
            priority=glib.PRIORITY_LOW)

    def capture_stop(self):
        # Unregister the image capturing subroutine.
        glib.source_remove(self.gio_tag)

    def run_once(self,
                 led_rounds=1, show_fps=False, single_shot=False):
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
            # Always on if only one round.
            self.ledstats = 1
        elif led_rounds > 1:
            # Ensure one on round and one off round.
            self.ledstats = randrange(2 ** led_rounds - 2) + 1
        self.show_fps = show_fps
        self.stage = 0

        self.label = label = gtk.Label(MESSAGE_STR)
        label.modify_font(LABEL_FONT)
        label.modify_fg(gtk.STATE_NORMAL, gdk.color_parse('light green'))

        test_widget = gtk.VBox()
        test_widget.modify_bg(gtk.STATE_NORMAL, gdk.color_parse('black'))
        test_widget.add(label)
        self.test_widget = test_widget

        self.img = None

        # Initialize the camera with OpenCV.  Since it's not too smart
        # about finding the device, try to find the device for it.  If
        # multiple devices are present, this grabs the last one.
        uvc_viddir = '/sys/bus/usb/drivers/uvcvideo'
        for uvc_direntry in os.listdir(uvc_viddir):
            if uvc_direntry[0].isdigit():
                uvc_subdir = os.path.join(uvc_viddir, uvc_direntry,
                                          'video4linux')
                if not os.path.isdir(uvc_subdir):
                    continue
                for uvc_devname in os.listdir(uvc_subdir):
                    if uvc_devname.startswith('video'):
                      DEVICE_INDEX = int(uvc_devname[5:])
        self.dev = dev = cv2.VideoCapture(DEVICE_INDEX)
        if not dev.isOpened():
            raise IOError('Device #%s ' % DEVICE_INDEX +
                             'does not support video capture interface')

        if single_shot:
            # Read image from camera.
            ret, cvImg = self.dev.read()
            if not ret:
                raise IOError("Error while capturing. Camera disconnected?")
        else:
            width, height = (dev.get(cv.CV_CAP_PROP_FRAME_WIDTH),
                    dev.get(cv.CV_CAP_PROP_FRAME_HEIGHT))

            # Initialize the canvas.
            self.pixbuf = gdk.Pixbuf(gdk.COLORSPACE_RGB, False, 8,
                width, height)
            self.img = gtk.image_new_from_pixbuf(self.pixbuf)
            self.test_widget.add(self.img)
            self.img.show()

            if self.show_fps:
                self.last_capture_time = time.clock()
                self.current_fps = PREFERRED_FPS

            self.capture_start()

            ful.run_test_widget(self.job, test_widget,
                window_registration_callback=self.register_callbacks)

            if self.fail:
                raise error.TestFail('Camera test failed by user '  \
                                     'indication\n品管人员怀疑摄影' \
                                     '镜头故障，请检修')
            if self.ledfail:
                raise error.TestFail('Camera LED test failed\n'  \
                                     '摄影镜头 LED 测试不通过，' \
                                     '请检修')

        factory.log('%s run_once finished' % self.__class__)
