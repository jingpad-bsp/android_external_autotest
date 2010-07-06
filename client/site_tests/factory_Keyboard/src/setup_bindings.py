#!/usr/bin/python
#
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cairo
import gobject
import gtk
import sys
import time
import os


_OUTPUT_HEADER = \
'''
# AUTOMATICALLY GENERATED -- This data structure is printed out by
# BindingsSetup during execution, and modifications can be pasted from
# there back to here.
'''


class BindingsSetup:
    """Facilitate generation of the binding map for the actual
    KeyboardTest -- it takes the name of a png keyboard image file and
    optionally a corresponding bindings file as its first and second
    command line arguments, respectively.  On each assignment of a new
    binding, it will output the contents for a new bindings file to
    stdout (a bit verbose, but simple).

    UI -- select key region to be highlighted with the mouse, hit
    corresponding key, double click to active tweak mode, fine tune
    highlighted region with the arrow keys (hold shift for neg
    effect), double click to confirm and output current bindings
    datastructure, repeat."""

    # Allow tweak mode adjustment of coords using the arrow keys.
    tweak_keys = {
        0xff51 : [1, 0, 0, 0],
        0xff52 : [0, 1, 0, 0],
        0xff53 : [0, 0, 1, 0],
        0xff54 : [0, 0, 0, 1]}

    def __init__(self, kbd_image, bindings):
        self._kbd_image = kbd_image
        self._press_xy = None
        self._last_coords = None
        self._last_key = None
        self._tweak_mode = False
        self._bindings = bindings

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
        print _OUTPUT_HEADER
        print ('\n{\n%s\n}' % ',\n'.join('    %s' % b for b in binding_list))

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
            delta = BindingsSetup.tweak_keys.get(event.keyval)
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
    window.connect('destroy', lambda w: gtk.main_quit())

    window.set_default_size(981, 450)

    bg_color = gtk.gdk.color_parse('midnight blue')
    window.modify_bg(gtk.STATE_NORMAL, bg_color)

    kbd_image = cairo.ImageSurface.create_from_png(sys.argv[1])
    kbd_image_size = (kbd_image.get_width(), kbd_image.get_height())

    bindings = {}
    if len(sys.argv) == 2 and os.path.exists(sys.argv[2]):
        f = open('sys.argv[2]' % layout, 'r')
        bindings = eval(f.read())
        f.close()

    drawing_area = gtk.DrawingArea()
    drawing_area.set_size_request(*kbd_image_size)

    kt = BindingsSetup(kbd_image, bindings)
    window.connect('key-press-event', kt.key_press_event)
    drawing_area.connect('button_release_event', kt.button_release_event)
    drawing_area.connect('button_press_event', kt.button_press_event)
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

if __name__ == '__main__':
    main()
