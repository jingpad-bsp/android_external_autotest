#!/usr/bin/python
#
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# DESCRIPTION :
#
# Intended for use during manufacturing to validate that all keyboard
# keys function properly.  Run normally, this program will display a
# keyboard image and keys will be highlighted as they are pressed and
# released.  Once all keys have been used, a brief 'PASS' message will
# be displayed and the test will terminate.  After the first key is
# hit, a countdown will begin.  If not all keys are used in time, the
# test will fail with an 'ERROR' message that is displayed forever.
# There is also a setup mode, to facilitate programming the expected
# key bindings, described in the KeyboardTestSetup class.

import cairo
import gobject
import gtk
import sys
import time

class KeyboardTest:

    # AUTOMATICALLY GENERATED -- This data structure is printed out by
    # KeyboardTestSetup during execution, and modifications can be
    # pasted from there back to here.
    bindings = {
        0x20   : (247,283,327, 57),
        0x27   : (712,163, 57, 57),
        0x2c   : (562,223, 57, 57),
        0x2d   : (667, 43, 57, 57),
        0x2e   : (622,223, 57, 57),
        0x2f   : (682,223, 57, 57),
        0x30   : (607, 43, 57, 57),
        0x31   : ( 67, 43, 57, 57),
        0x32   : (127, 43, 57, 57),
        0x33   : (187, 43, 57, 57),
        0x34   : (247, 43, 57, 57),
        0x35   : (307, 43, 57, 57),
        0x36   : (367, 43, 57, 57),
        0x37   : (427, 43, 57, 57),
        0x38   : (487, 43, 57, 57),
        0x39   : (547, 43, 57, 57),
        0x3b   : (652,163, 57, 57),
        0x3d   : (727, 43, 57, 57),
        0x5b   : (697,103, 57, 57),
        0x5c   : (817,103, 87, 57),
        0x5d   : (757,103, 57, 57),
        0x60   : (  7, 43, 57, 57),
        0x61   : (112,163, 57, 57),
        0x62   : (382,223, 57, 57),
        0x63   : (262,223, 57, 57),
        0x64   : (232,163, 57, 57),
        0x65   : (217,103, 57, 57),
        0x66   : (292,163, 57, 57),
        0x67   : (352,163, 57, 57),
        0x68   : (412,163, 57, 57),
        0x69   : (517,103, 57, 57),
        0x6a   : (472,163, 57, 57),
        0x6b   : (532,163, 57, 57),
        0x6c   : (592,163, 57, 57),
        0x6d   : (502,223, 57, 57),
        0x6e   : (442,223, 57, 57),
        0x6f   : (577,103, 57, 57),
        0x70   : (637,103, 57, 57),
        0x71   : ( 97,103, 57, 57),
        0x72   : (277,103, 57, 57),
        0x73   : (172,163, 57, 57),
        0x74   : (337,103, 57, 57),
        0x75   : (457,103, 57, 57),
        0x76   : (322,223, 57, 57),
        0x77   : (157,103, 57, 57),
        0x78   : (202,223, 57, 57),
        0x79   : (397,103, 57, 57),
        0x7a   : (142,223, 57, 57),
        0xff08 : (787, 43,117, 57),
        0xff09 : (  7,103, 87, 57),
        0xff0d : (772,163,132, 57),
        0xff1b : (  7,  9, 87, 24),
        0xff51 : (727,283, 57, 57),
        0xff52 : (787,283, 57, 28),
        0xff53 : (847,283, 57, 57),
        0xff54 : (787,314, 57, 26),
        0xffbe : (121,  9, 57, 24),
        0xffbf : (181,  9, 57, 24),
        0xffc0 : (265,  9, 57, 24),
        0xffc1 : (325,  9, 57, 24),
        0xffc2 : (385,  9, 57, 24),
        0xffc3 : (469,  9, 57, 24),
        0xffc4 : (529,  9, 57, 24),
        0xffc5 : (613,  9, 57, 24),
        0xffc6 : (673,  9, 57, 24),
        0xffc7 : (733,  9, 57, 24),
        0xffe1 : (  7,223,132, 57),
        0xffe2 : (742,223,162, 57),
        0xffe3 : (  7,283,117, 57),
        0xffe4 : (652,283, 72, 57),
        0xffe5 : (  7,163, 87, 57),
        0xffe9 : (127,283,117, 57),
        0xffea : (577,283, 72, 57)
    }

    # How long KeyboardTest allows in seconds from the first keypress
    # until defaulting to the failure condition.
    timeout = 50

    # How long to display the success message in seconds before exit.
    pass_msg_timeout = 2

    # Background color and alpha for the final result message.
    bg_rgba_error = (0.7,   0, 0, 0.9)
    bg_rgba_pass =  (  0, 0.7, 0, 0.9)

    # Highlight color and alpha to indicate activated keys.
    rgba_press_and_release = (  0, 0.5, 0, 0.6)
    rgba_press_only =        (0.6, 0.6, 0, 0.6)

    def __init__(self, kbd_image, exit_on_error=False):
        self._kbd_image = kbd_image
        self._exit_on_error = exit_on_error
        self._pressed_keys = set()
        self._successful_keys = set()
        self._deadline = None
        self._success = None

    def missing_keys(self):
        return set(KeyboardTest.bindings) - self._successful_keys

    def show_result(self, widget, context, text, bg_rgba):
        widget_width, widget_height = widget.get_size_request()
        context.save()
        context.scale(widget_width / 1.0, widget_height / 1.0)
        context.rectangle(0.05, 0.05, 0.9, 0.9)
        context.set_source_rgba(*bg_rgba)
        context.fill()
        context.set_source_rgba(0.1, 0.1, 0.1, 0.95)
        context.select_font_face(
            'Verdana', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(0.2)
        x_bearing, y_bearing, width, height = context.text_extents(text)[:4]
        context.move_to(0.5 - (width / 2) - x_bearing,
                        0.5 - (height / 2) - y_bearing)
        context.show_text(text)
        context.restore()

    def start_countdown(self, duration):
        self._deadline = int(time.time()) + duration

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
            self._deadline = None
            if self._success is None:
                self._success = False
                mk = ['0x%x' % k for k in self.missing_keys()]
                print 'missing_keys = %s' % ', '.join(mk)
                if self._exit_on_error:
                    sys.exit(1)
            elif self._success:
                sys.exit(0)
        window.queue_draw()
        return True

    def expose_event(self, widget, event):
        context = widget.window.cairo_create()

        # Show keyboard image as the background.
        context.set_source_surface(self._kbd_image, 0, 0)
        context.paint()

        # Boolean values for success correspond with test pass or
        # failure.  None means normal operation.
        if self._success is None:
            for key in self._successful_keys:
                coords = KeyboardTest.bindings[key]
                context.rectangle(*coords)
                context.set_source_rgba(*KeyboardTest.rgba_press_and_release)
                context.fill()
            for key in self._pressed_keys:
                coords = KeyboardTest.bindings[key]
                context.rectangle(*coords)
                context.set_source_rgba(*KeyboardTest.rgba_press_only)
                context.fill()
            if self._deadline:
                self.show_countdown(widget, context)
        elif self._success:
            self.show_result(widget, context, 'PASS',
                             KeyboardTest.bg_rgba_pass)
        else:
            self.show_result(widget, context, 'ERROR',
                             KeyboardTest.bg_rgba_error)
        return False

    def key_press_event(self, widget, event):
        if (self._success is False
            and event.keyval == gtk.keysyms.q
            and 'GDK_CONTROL_MASK' in event.state.value_names):
            # Allow Ctrl-q to exit from the ERROR screen.
            sys.exit(1)
        if self._success is not None or event.keyval in self._successful_keys:
            # Ignore key presses once a success condition exists.
            # Also ignore pressed for keys already found to work
            # successfully.
            return True
        if event.state != 0:
            print ('warning: key ignored because modifier applied (state=%d)'
                   % event.state)
            return True
        if event.keyval not in KeyboardTest.bindings:
            print 'ERROR: key 0x%x not found in bindings' % event.keyval
            return True

        self._pressed_keys.add(event.keyval)
        widget.queue_draw()

        # The first keypress starts test countdown.
        if self._deadline is None:
            self.start_countdown(KeyboardTest.timeout)

        return True

    def key_release_event(self, widget, event):
        if self._success is not None or event.keyval not in self._pressed_keys:
            # Ignore key releases once a success condition exists.
            # Also ignore releases for keys not previously accepted as
            # pressed.
            return True
        else:
            self._pressed_keys.remove(event.keyval)
            self._successful_keys.add(event.keyval)
            if not self.missing_keys():
                self._success = True
                self.start_countdown(KeyboardTest.pass_msg_timeout)
            widget.queue_draw()
        return True

class KeyboardTestSetup:
    """Facilitate generation of the binding map for the actual
    KeyboardTest.  UI -- select key region to be highlighted with the
    mouse, hit corresponding key, double click to active tweak mode,
    fine tune highlighted region with the arrow keys (hold shift for
    neg effect), double click to confirm and output current bindings
    datastructure, repeat."""

    # Allow tweak mode adjustment of coords using the arrow keys.
    tweak_keys = {
        0xff51 : [1, 0, 0, 0],
        0xff52 : [0, 1, 0, 0],
        0xff53 : [0, 0, 1, 0],
        0xff54 : [0, 0, 0, 1]}

    def __init__(self, kbd_image):
        self._kbd_image = kbd_image
        self._press_xy = None
        self._last_coords = None
        self._last_key = None
        self._tweak_mode = False
        self._bindings = KeyboardTest.bindings

    def fmt_coords(self, coords):
        return '%3d,%-3d %2dx%-2d' % coords

    def fmt_key(self, key):
        return '%4x,%-4x' % key

    def fmt_binding(self, binding):
        key, coords = binding
        return '0x%-4x : %s' % (key, '(%3d,%3d,%3d,%3d)' % coords)

    def tweak_coords(self, d_lft, d_top, d_rgt, d_bot):
        xmin, ymin, xdelta, ydelta = self._last_coords
        xmin -= d_lft
        ymin -= d_top
        xdelta += d_lft + d_rgt
        ydelta += d_top + d_bot
        self._last_coords = (xmin, ymin, xdelta, ydelta)

    def confirm_binding(self):
        kc, kv = self._last_key
        self._bindings[kc] = self._last_coords
        binding_list = [self.fmt_binding(b) for b in
                        sorted(self._bindings.items())]
        print ('    bindings = {\n%s\n    }' %
               ',\n'.join('        %s' % b for b in binding_list))

    def expose_event(self, widget, event):
        context = widget.window.cairo_create()
        context.set_source_surface(self._kbd_image, 0, 0)
        context.paint()
        if self._last_coords:
            context.rectangle(*self._last_coords)
            context.set_source_rgba(0, 0.5, 0, 0.6)
            context.fill()
        return False

    def button_press_event(self, widget, event):
        if not event.button == 1:
            return False
        if self._tweak_mode:
            if event.type == gtk.gdk._2BUTTON_PRESS:
                self.confirm_binding()
                self._tweak_mode = False
                self._press_xy = None
                self._last_coords = None
                self._last_key = None
        else:
            if (event.type == gtk.gdk._2BUTTON_PRESS and
                self._last_coords and self._last_key):
                self._tweak_mode = True
                print 'tweak mode'
            else:
                self._press_xy = (event.x, event.y)
        return True

    def button_release_event(self, widget, event):
        if not event.button == 1:
            return False
        if (not self._tweak_mode) and self._press_xy:
            px, py = self._press_xy
            xmin, xmax = sorted([px, event.x])
            ymin, ymax = sorted([py, event.y])
            xdelta = xmax - xmin
            ydelta = ymax - ymin
            if xdelta and ydelta:
                self._last_coords = (xmin, ymin, xdelta, ydelta)
                print 'coords %s' % self.fmt_coords(self._last_coords)
                widget.queue_draw()
        return True

    def key_press_event(self, widget, event):
        key = (event.keyval, event.hardware_keycode)
        if self._tweak_mode:
            delta = KeyboardTestSetup.tweak_keys.get(event.keyval)
            if delta:
                if 'GDK_SHIFT_MASK' in event.state.value_names:
                    # Reverse the effect if SHIFT is being held down.
                    delta = map((lambda x: 0 - x), delta)
                self.tweak_coords(*delta)
                print 'tweak %s --> %s' % (self.fmt_key(self._last_key),
                                           self.fmt_coords(self._last_coords))
                widget.queue_draw()
        else:
            self._last_key = key
            print 'key    %s %s' % (self.fmt_key(key), repr(event.string))
        return True

def main():
    window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    window.set_name ('Keyboard Test')
    window.connect('destroy', lambda w: gtk.main_quit())

    bg_color = gtk.gdk.color_parse('midnight blue')
    window.modify_bg(gtk.STATE_NORMAL, bg_color)

    kbd_image = cairo.ImageSurface.create_from_png('kbd.png')
    kbd_image_size = (kbd_image.get_width(), kbd_image.get_height())

    drawing_area = gtk.DrawingArea()
    drawing_area.set_size_request(*kbd_image_size)

    if len(sys.argv) > 1 and sys.argv[1] == '--setup':
        kt = KeyboardTestSetup(kbd_image)
        window.set_default_size(981, 450)
        window.connect('key-press-event', kt.key_press_event)
        drawing_area.connect('button_release_event', kt.button_release_event)
        drawing_area.connect('button_press_event', kt.button_press_event)
    else:
        exit_on_error = False
        if '--exit-on-error' in sys.argv:
            exit_on_error = True
        kt = KeyboardTest(kbd_image, exit_on_error=exit_on_error)
        screen = window.get_screen()
        screen_size = (screen.get_width(), screen.get_height())
        window.set_default_size(*screen_size)
        window.connect('key-press-event', kt.key_press_event)
        window.connect('key-release-event', kt.key_release_event)
        gobject.timeout_add(1000, kt.timer_event, window)

    drawing_area.connect('expose_event', kt.expose_event)

    drawing_area.show()

    align = gtk.Alignment(xalign=0.5, yalign=0.5)
    align.add(drawing_area)
    align.show()

    drawing_area.set_events(gtk.gdk.EXPOSURE_MASK |
                            gtk.gdk.KEY_PRESS_MASK |
                            gtk.gdk.BUTTON_PRESS_MASK |
                            gtk.gdk.BUTTON_RELEASE_MASK)

    window.add(align)
    window.show()

    gtk.main()

    return (kt.success != True)

if __name__ == '__main__':
    main()
