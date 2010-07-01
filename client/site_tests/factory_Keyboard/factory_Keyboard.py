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
import pango
import time
import os
import sys

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_test
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


# How long keyboard_test allows in seconds from the first keypress
# until defaulting to the failure condition.
_TIMEOUT = 50
_PASS_TIMEOUT = 0.4

# Highlight color and alpha to indicate activated keys.
_RGBA_PRESS_AND_RELEASE = (  0, 0.5, 0, 0.6)
_RGBA_PRESS_ONLY =        (0.6, 0.6, 0, 0.6)


class KeyboardTest:

    def __init__(self, kbd_image, bindings, ft_state):
        self._kbd_image = kbd_image
        self._bindings = bindings
        self._ft_state = ft_state
        self._pressed_keys = set()
        self._successful_keys = set()
        self._deadline = None
        self._success = False

    def show_countdown(self, widget, context):
        countdown = self._deadline - int(time.time())
        width, height = widget.get_size_request()
        text = '%3d' % countdown
        context.save()
        context.translate(width - 60, height)
        context.set_source_rgb(0.5, 0.5, 0.5)
        context.select_font_face(
            'Courier New', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        context.set_font_size(20)
        x_bearing, y_bearing = context.text_extents('000')[:2]
        context.move_to(x_bearing, y_bearing)
        context.show_text(text)
        context.restore()

    def timer_event(self, window):
        if not self._deadline:
            # Ignore timer events with no countdown in progress.
            return True
        if self._deadline <= time.time():
            factory.log('deadline reached')
            gtk.main_quit()
        window.queue_draw()
        return True

    def expose_event(self, widget, event):
        context = widget.window.cairo_create()

        # Show keyboard image as the background.
        context.set_source_surface(self._kbd_image, 0, 0)
        context.paint()

        for key in self._successful_keys:
            coords = self._bindings[key]
            context.rectangle(*coords)
            context.set_source_rgba(*_RGBA_PRESS_AND_RELEASE)
            context.fill()
        for key in self._pressed_keys:
            coords = self._bindings[key]
            context.rectangle(*coords)
            context.set_source_rgba(*_RGBA_PRESS_ONLY)
            context.fill()
        if self._deadline:
            self.show_countdown(widget, context)

        return True

    def key_press_event(self, widget, event):
        if self._ft_state.exit_on_trigger(event):
            return True
        if ('GDK_MOD1_MASK' in event.state.value_names
            and event.keyval == gtk.keysyms.q):
            # Alt-q for early exit.
            gtk.main_quit()
            return True
        if event.keyval in self._successful_keys:
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
            self._deadline = int(time.time()) + _TIMEOUT

        return True

    def key_release_event(self, widget, event):
        if event.keyval not in self._pressed_keys:
            # Ignore releases for keys not previously accepted as pressed.
            return False
        self._pressed_keys.remove(event.keyval)
        self._successful_keys.add(event.keyval)
        if not (set(self._bindings) - self._successful_keys):
            self._success = True
            self._deadline = int(time.time()) + _PASS_TIMEOUT
        widget.queue_draw()
        return True

    def register_callbacks(self, window):
        window.connect('key-press-event', self.key_press_event)
        window.connect('key-release-event', self.key_release_event)
        window.add_events(gtk.gdk.KEY_PRESS_MASK | gtk.gdk.KEY_RELEASE_MASK)


class factory_Keyboard(test.test):
    version = 1
    preserve_srcdir = True

    def run_once(self,
                 test_widget_size=None,
                 trigger_set=None,
                 result_file_path=None,
                 layout=None):

        factory.log('%s run_once' % self.__class__)

        # XXX Why can this not be run from the UI code?
        xset_status = os.system('xset r off')
        xmm_status = os.system('xmodmap -e "clear Lock"')
        if xset_status or xmm_status:
            raise TestFail('ERROR: disabling key repeat or caps lock')

        ft_state = factory_test.State(
            trigger_set=trigger_set,
            result_file_path=result_file_path)

        os.chdir(self.srcdir)

        kbd_image = cairo.ImageSurface.create_from_png('%s.png' % layout)
        image_size = (kbd_image.get_width(), kbd_image.get_height())

        with open('%s.bindings' % layout, 'r') as file:
            bindings = eval(file.read())

        test = KeyboardTest(kbd_image, bindings, ft_state)

        drawing_area = gtk.DrawingArea()
        drawing_area.set_size_request(*image_size)
        drawing_area.connect('expose_event', test.expose_event)
        drawing_area.add_events(gtk.gdk.EXPOSURE_MASK)
        gobject.timeout_add(1000, test.timer_event, drawing_area)

        ft_state.run_test_widget(
            test_widget=drawing_area,
            test_widget_size=test_widget_size,
            window_registration_callback=test.register_callbacks)

        factory.log('%s run_once finished' % self.__class__)
