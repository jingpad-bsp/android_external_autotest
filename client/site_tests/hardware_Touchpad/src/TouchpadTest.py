#!/usr/bin/python
#
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# DESCRIPTION :
#
# Intended for use during manufacturing to validate that all touchpad
# features function properly. Run normally, this program will display a
# touchpad image and buttons will be highlighted as they are pressed and
# released. Once all functions have been used, a brief 'PASS' message will
# be displayed and the test will terminate.  After the first button is
# hit, a countdown will begin.  If not all buttons are used in time, the
# test will fail with an 'ERROR' message that is displayed forever.

import cairo
import gobject
import gtk
import os
import sys
import time

class Button:
    def __init__(self, coords):
        self._pressed = False
        self._released = False
        self._coords = coords

class TouchpadTest:
    # Coordinates of buttons we need to highlight.
    left_button_coords =  (65, 321, 255, 93)
    right_button_coords = (321, 321, 254, 93)

    # How long TouchpadTest allows in seconds from the first move or button
    # pressed until defaulting to the failure condition.
    timeout = 50

    # How long to display the success message in seconds before exit.
    pass_msg_timeout = 2

    # Background color and alpha for the final result message.
    bg_rgba_error = (0.7,   0, 0, 0.9)
    bg_rgba_pass =  (  0, 0.7, 0, 0.9)

    # Highlight color and alpha to indicate activated keys.
    rgba_press_and_release = (  0, 0.5, 0, 0.6)
    rgba_press_only =        (0.6, 0.6, 0, 0.6)
    
    def __init__(self, image, exit_on_error=False):
        self._image = image
        self._exit_on_error = exit_on_error
        self._deadline = None
        self._success = None
        self._buttons = {}
        self._buttons[1] = Button(TouchpadTest.left_button_coords)
        self._buttons[3] = Button(TouchpadTest.right_button_coords)

    def has_test_passed(self):
        for key in self._buttons.keys():
            if (not self._buttons[key]._pressed or
                not self._buttons[key]._released):
                return False
        return True

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
                if self._exit_on_error:
                    sys.exit(1)
            elif self._success:
                sys.exit(0)
        window.queue_draw()
        return True

    def expose_event(self, widget, event):
        context = widget.window.cairo_create()

        # Show touchpad image as the background.
        context.set_source_surface(self._image, 0, 0)
        context.paint()

        # Boolean values for success correspond with test pass or
        # failure. None means normal operation.
        if self._success is None:
            for key in self._buttons.keys():
                color = None
                if self._buttons[key]._released:
                    color = TouchpadTest.rgba_press_and_release
                elif self._buttons[key]._pressed:
                    color = TouchpadTest.rgba_press_only
                else:
                    continue
                coords = self._buttons[key]._coords
                context.rectangle(*coords)
                context.set_source_rgba(*color)
                context.fill()
            if self._deadline:
                self.show_countdown(widget, context)
        elif self._success:
            self.show_result(widget, context, 'PASS',
                             TouchpadTest.bg_rgba_pass)
        else:
            self.show_result(widget, context, 'ERROR',
                             TouchpadTest.bg_rgba_error)
        return False

    def button_press_event(self, widget, event):
        if self._success is not None:
            return True
        if not event.button in self._buttons.keys():
            return True

        if self._deadline is None:
            self.start_countdown(TouchpadTest.timeout)
        self._buttons[event.button]._pressed = True
        widget.queue_draw()
        return True

    def button_release_event(self, widget, event):
        if self._success is not None:
            return True
        if not event.button in self._buttons.keys():
            return True

        self._buttons[event.button]._released = True
        if self.has_test_passed():
            self._success = True
            self.start_countdown(TouchpadTest.pass_msg_timeout)
        widget.queue_draw()
        return True

def main():
    window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    window.set_name('Touchpad Test')
    window.connect('destroy', lambda w: gtk.main_quit())

    bg_color = gtk.gdk.color_parse('midnight blue')
    window.modify_bg(gtk.STATE_NORMAL, bg_color)

    touchpad_image = cairo.ImageSurface.create_from_png('touchpad.png')
    touchpad_image_size = (touchpad_image.get_width(),
                           touchpad_image.get_height())

    drawing_area = gtk.DrawingArea()
    drawing_area.set_size_request(*touchpad_image_size)

    exit_on_error = False
    if '--exit-on-error' in sys.argv:
        exit_on_error = True
    tt = TouchpadTest(touchpad_image, exit_on_error=exit_on_error)
    screen = window.get_screen()
    screen_size = (screen.get_width(), screen.get_height())
    window.set_default_size(*screen_size)
    window.connect('button_press_event', tt.button_press_event)
    window.connect('button_release_event', tt.button_release_event)
    gobject.timeout_add(1000, tt.timer_event, window)

    drawing_area.connect('expose_event', tt.expose_event)

    drawing_area.show()

    align = gtk.Alignment(xalign=0.5, yalign=0.5)
    align.add(drawing_area)
    align.show()

    drawing_area.set_events(gtk.gdk.EXPOSURE_MASK |
                            gtk.gdk.BUTTON_PRESS_MASK |
                            gtk.gdk.BUTTON_RELEASE_MASK)

    window.add(align)
    window.show()

    gtk.main()

    return (tt._success != True)

if __name__ == '__main__':
    main()
