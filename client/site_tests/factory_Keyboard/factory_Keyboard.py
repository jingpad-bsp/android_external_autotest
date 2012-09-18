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

import re
import subprocess

from gtk import gdk

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory_setup_modules
from cros.factory.test import factory
from cros.factory.test import ui as ful

# The keycodes from the GTK keyboard event have a +8 offset
# from the real one, hence the constant here
_GTK_KB_KEYCODE_OFFSET = 8

# GTK keycode for left Ctrl, Alt and Shift.
_LCTRL = 37
_LALT = 64
_LSHIFT = 50

# GTK state mask for key combination.
_MOD_MASK = gtk.gdk.CONTROL_MASK | gtk.gdk.MOD1_MASK | gtk.gdk.SHIFT_MASK

def GenerateKeycodeBinding(old_bindings):
    '''Offsets the bindings keycodes for GTK.'''
    key_to_geom = {}
    for item in old_bindings.items():
        key_to_geom[item[0] + _GTK_KB_KEYCODE_OFFSET] = item[1]
    return key_to_geom

class KeyboardTest:
    '''Keyboard test.

    Args:
      kbd_image: Keyboard image file
      binding: Keyboard binding file
      scale: image scaling factor
      accept_combi_key: (bool) True to accept combination key.
    '''

    def __init__(self, kbd_image, bindings, scale, accept_combi_key):
        self._kbd_image = kbd_image
        self._bindings = bindings
        self._scale = scale
        self._pressed_keys = set()
        self._deadline = None
        self.successful_keys = set()
        self._accept_combi_key = accept_combi_key

    def calc_missing_string(self):
        missing_keys = sorted((gdk.keyval_name(k) or '<0x%x>' % k)for k in
                              set(self._bindings) - self.successful_keys)
        if not missing_keys:
            return ''
        return ('Missing following keys\n' +
                '没有侦测到下列按键，键盘可能故障，请检修: %s' %
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
        context.scale(self._scale, self._scale)
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

    def get_combined_keycode(self, event):
        '''Gets combined keycode.

        If Ctrl/Alt/Shift is also presented in key event, returns
        hardware_keycode + offset:
          Shift: 256
          Ctrl: 1024
          Alt: 2048

        Args:
          event: GTK event.

        Returns:
          Combined keycode explained above.
        '''
        return event.hardware_keycode + ((event.state & _MOD_MASK) << 8)

    def process_combi_key_press_event(self, event):
        '''Processes key-press event with combination key.

        Args:
          event: GTK event.

        Returns:
          (accept, keycode):
            accept == True if the key is in _bindings.
            keycode: combined keycode. Refer get_combined_keycode().
        '''
        keycode = self.get_combined_keycode(event)
        if keycode in self._bindings:
            # Known issue: if you press left Ctrl then "New Tab (Ctrl-T)", and
            # then release them, the left Ctrl will be discarded unexpectedly.
            # However, as it only hapeends when an operator sweeps keyboard
            # and presses left Ctrl first then "New Tab", which is rare. And
            # if it happends, operator can hit left Ctrl again to fix the
            # issue. So I will leave the issue open until we found a nice fix.
            if event.state & gtk.gdk.CONTROL_MASK:
                self._pressed_keys.discard(_LCTRL)
            if event.state & gtk.gdk.MOD1_MASK:
                self._pressed_keys.discard(_LALT)
            if event.state & gtk.gdk.SHIFT_MASK:
                self._pressed_keys.discard(_LSHIFT)
        elif event.hardware_keycode in self._bindings:
            # For those unbinded key combinations, treat them as only
            # base keys are pressed.
            keycode = event.hardware_keycode
        else:
            return False, 0
        return True, keycode

    def process_simple_key_press_event(self, event):
        '''Processes key-press event regardless key combination.

        Args:
          event: GTK event.

        Returns:
          (accept, keycode):
            accept == True if the key is in _bindings.
            keycode: hardware_keycode.
        '''
        keycode = event.hardware_keycode
        return keycode in self._bindings, keycode

    def key_press_event(self, widget, event):
        accept = False
        if self._accept_combi_key:
            accept, keycode = self.process_combi_key_press_event(event)
        else:
            accept, keycode = self.process_simple_key_press_event(event)
        if not accept:
            factory.log('key (0x%x) ignored because not in bindings'
                        % event.keyval)
            return True

        self._pressed_keys.add(keycode)
        widget.queue_draw()

        # The first keypress starts test countdown.
        if self._deadline is None:
            self._deadline = int(time.time()) + ful.FAIL_TIMEOUT

        return True

    def key_release_event(self, widget, event):
        hardware_keycode_check = True
        if self._accept_combi_key:
            keycode = self.get_combined_keycode(event)
            # If combined keycode is not pressed before, fall back to check
            # hardware_keycode instead.
            hardware_keycode_check = keycode not in self._pressed_keys
        if hardware_keycode_check:
            keycode = event.hardware_keycode
            if keycode not in self._pressed_keys:
                # Ignore releases for keys not previously accepted as pressed.
                return False
        self._pressed_keys.remove(keycode)
        self.successful_keys.add(keycode)
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
       """ vpd should contain
          "initial_locale"="en-US"
          "keyboard_layout"="xkb:us::eng"
       or similar. """
       cmd = 'vpd -l | grep initial_locale | cut -f4 -d\'"\''
       layout = utils.system_output(cmd).strip()
       if layout != '':
           return layout
       return None

    def run_once(self, layout=None, combi_key=False, config_dir=''):
        '''

        Args:
          layout: use specified layout other than derived from VPD.
          combi_key: True to handle key combination.
          config_dir: specify directory to read keyboard image and binding
             from. If unspeified, read from default directory.
        '''

        factory.log('%s run_once' % self.__class__)

        os.chdir(self.srcdir)

        # Autodetect from VPD.
        if not layout:
            layout = self.get_layout_from_vpd()
        # Default to United States.
        if not layout:
            layout = 'en-US'

        factory.log("Using keyboard layout %s" % layout)
        layout_filename = os.path.join(config_dir, '%s.png' % layout)
        try:
            kbd_image = cairo.ImageSurface.create_from_png(layout_filename)
            image_size = (kbd_image.get_width(), kbd_image.get_height())
        except cairo.Error as e:
            raise error.TestNAError('Error while opening %s: %s' %
                                    (layout_filename, e.message))

        bindings_filename = os.path.join(config_dir, '%s.bindings' % layout)
        try:
            with open(bindings_filename, 'r') as file:
                bindings = eval(file.read())
                bindings = GenerateKeycodeBinding(bindings)
        except IOError as e:
            raise error.TestNAError('Error while opening %s: %s [Errno %d]' %
                                    (e.filename, e.strerror, e.errno))

        scale = ful.calc_scale(*image_size)

        test = KeyboardTest(kbd_image, bindings, scale, combi_key)

        scaled_image_size = (image_size[0] * scale, image_size[1] * scale)

        drawing_area = gtk.DrawingArea()
        drawing_area.set_size_request(*scaled_image_size)
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
