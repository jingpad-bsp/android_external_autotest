# -*- coding: utf-8 -*-
#
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# Intended for use during manufacturing to validate that all keyboard
# keys function properly.  This program will display a keyboard image
# and keys will be highlighted as they are pressed and released.
# After the first key is hit, a countdown will begin.  If not all keys
# are used in time, the test will fail.


import cairo
import gobject
import gtk
import logging
import time
import os
import sys
import utils

from gtk import gdk

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


class KeyboardTest:

    def __init__(self, kbd_image, bindings):
        self._kbd_image = kbd_image
        self._bindings = bindings
        self._pressed_keys = set()
        self._deadline = None
        self.successful_keys = set()

    def calc_missing_string(self):
        missing_keys = sorted(gdk.keyval_name(k) for k in
                              set(self._bindings) - self.successful_keys)
        if not missing_keys:
            return ''
        return ('Missing following keys\n' +
                '沒有偵測到下列按鍵，鍵盤可能故障，請檢修: %s' %
                ', '.join(missing_keys))

    def timer_event(self, countdown_label):
        if not self._deadline:   # Ignore timer with no countdown in progress.
            return True
        time_remaining = max(0, self._deadline - time.time())
        if time_remaining == 0:
            factory.log('deadline reached')
            gtk.main_quit()
        countdown_label.set_text('%d' % time_remaining)
        countdown_label.queue_draw()
        return True

    def expose_event(self, widget, event):
        context = widget.window.cairo_create()

        # Show keyboard image as the background.
        context.set_source_surface(self._kbd_image, 0, 0)
        context.paint()

        for key in self.successful_keys:
            coords = self._bindings[key]
            context.rectangle(*coords)
            context.set_source_rgba(*ful.RGBA_GREEN_OVERLAY)
            context.fill()
        for key in self._pressed_keys:
            coords = self._bindings[key]
            context.rectangle(*coords)
            context.set_source_rgba(*ful.RGBA_YELLOW_OVERLAY)
            context.fill()

        return True

    def key_press_event(self, widget, event):
        if ('GDK_MOD1_MASK' in event.state.value_names
            and event.keyval == gtk.keysyms.q):
            # Alt-q for early exit.
            gtk.main_quit()
            return True
        if event.keyval in self.successful_keys:
            # Ignore keys already found to work successfully.
            return True
        if event.state != 0:
            factory.log('key (0x%x) ignored because modifier applied (state=%d)'
                        % (event.keyval, event.state))
            return True
        if event.keyval not in self._bindings:
            factory.log('key (0x%x) ignored because not in bindings'
                        % event.keyval)
            return True

        self._pressed_keys.add(event.keyval)
        widget.queue_draw()

        # The first keypress starts test countdown.
        if self._deadline is None:
            self._deadline = int(time.time()) + ful.FAIL_TIMEOUT

        return True

    def key_release_event(self, widget, event):
        if event.keyval not in self._pressed_keys:
            # Ignore releases for keys not previously accepted as pressed.
            return False
        self._pressed_keys.remove(event.keyval)
        self.successful_keys.add(event.keyval)
        widget.queue_draw()
        if not self.calc_missing_string():
            factory.log('completed successfully')
            gtk.main_quit()
        return True

    def register_callbacks(self, window):
        window.connect('key-press-event', self.key_press_event)
        window.connect('key-release-event', self.key_release_event)
        window.add_events(gdk.KEY_PRESS_MASK | gdk.KEY_RELEASE_MASK)


class factory_Keyboard(test.test):
    version = 1
    preserve_srcdir = True

    def get_layout_from_vpd(self):
       """ vpd should contain "initial_locale"="en-US" or similar. """
       cmd = 'vpd -l | grep initial_locale | cut -f4 -d\'"\''
       layout = utils.system_output(cmd).strip()
       if layout != '':
           return layout
       return None

    def run_once(self, layout=None):

        factory.log('%s run_once' % self.__class__)

        os.chdir(self.srcdir)

        # Autodetect from VPD.
        if not layout:
            layout = self.get_layout_from_vpd()
        # Default to United States.
        if not layout:
            layout = 'en-US'

        factory.log("Using keyboard layout %s" % layout)
        try:
            kbd_image = cairo.ImageSurface.create_from_png('%s.png' % layout)
            image_size = (kbd_image.get_width(), kbd_image.get_height())
        except cairo.Error as e:
            raise error.TestNAError('Error while opening %s.png: %s' %
                                    (layout, e.message))

        try:
            with open('%s.bindings' % layout, 'r') as file:
                bindings = eval(file.read())
        except IOError as e:
            raise error.TestNAError('Error while opening %s: %s [Errno %d]' %
                                    (e.filename, e.strerror, e.errno))

        test = KeyboardTest(kbd_image, bindings)

        drawing_area = gtk.DrawingArea()
        drawing_area.set_size_request(*image_size)
        drawing_area.connect('expose_event', test.expose_event)
        drawing_area.add_events(gdk.EXPOSURE_MASK)

        countdown_widget, countdown_label = ful.make_countdown_widget()
        gobject.timeout_add(1000, test.timer_event, countdown_label)

        test_widget = gtk.VBox()
        test_widget.set_spacing(20)
        test_widget.pack_start(drawing_area, False, False)
        test_widget.pack_start(countdown_widget, False, False)

        ful.run_test_widget(self.job, test_widget,
            window_registration_callback=test.register_callbacks)

        missing = test.calc_missing_string()
        if missing:
            raise error.TestFail(missing)

        factory.log('%s run_once finished' % self.__class__)
