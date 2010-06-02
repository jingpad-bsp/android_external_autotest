#!/usr/bin/python
#
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# DESCRIPTION :
#
# Intended for use during manufacturing to validate that developer
# switch and recovery button function properly.  Run normally, test
# will display an D-housing image identifying where recovery button and
# developer switch are located.  It will highlight when recovery has
# been pressed and released.  It will highlight when developer switch
# has been switched & unswitched.  If successful, a brief 'PASS' message
# will be displayed and the test will terminate.  If not, the test will
# fail with an 'ERROR' message that is displayed forever (unless the
# 'hwqual' argument is passed in).

import cairo
import gobject
import gtk
import sys
import time
import os
import math 

class DevRecTest():

    gpio_info = {
        'developer' : {'type' : 'switch',
                       'cx' : 355,
                       'cy' : 175,
                       'size' : 30,
                       'arrow' : {'x' : 305,
                                  'y' : 175,
                                  'width' : 15,
                                  'length' : 100,
                                  # in degrees starts as rt arrow
                                  'direction' : 0,
                                  },
                       },
        'recovery' : {'type' : 'button',
                      'cx' : 635,
                      'cy' : 450,
                      'size' : 30,
                      'arrow' : {'x' : 580,
                                 'y' : 450,
                                 'width' : 15,
                                 'length' : 100,
                                 'direction' : 270,
                                 }
                      },
        }

    # How long DevRecTest allows in seconds until failing
    timeout = 20

    # How long to display the success message in seconds before exit.
    pass_msg_timeout = 2

    # Background color and alpha for the final result message.
    bg_rgba_fail = (0.7,   0, 0, 0.9)
    bg_rgba_pass = (  0, 0.7, 0, 0.9)

    rgba_state = [(0.0, 1.0, 0.0, 0.9),
                  (0.9, 0.9, 0.0, 0.6), 
                  (0.9, 0.0, 0.0, 0.6)]

    def __init__(self, devrec_image, exit_on_error=False):
        self._devrec_image = devrec_image
        self._exit_on_error = exit_on_error
        self._successful = set()
        self._deadline = None
        self._success = None
        self.gpios = devrec_gpio()
        self.gpios.cfg()

    def show_arrow(self, context, cx, cy, headx, heady, awidth, length,
                   degrees):

        '''Draw a simple arrow in given context.
        '''

        context.save()

        # rotation transform
        matrix = cairo.Matrix(1, 0, 0, 1, 0, 0)
        context.set_source_rgba(0, 0, 0, 1)
        cairo.Matrix.translate(matrix, cx, cy)
        cairo.Matrix.rotate(matrix, math.radians(degrees))
        cairo.Matrix.translate(matrix, -cx, -cy)
        context.transform(matrix)
        
        # right arrow default
        context.set_line_width(5)
        context.move_to(headx, heady)
        context.rel_line_to(-awidth, -awidth/2.0)
        context.rel_line_to(0, awidth)
        context.rel_line_to(awidth, -awidth/2.0)
        context.fill_preserve()
        context.rel_line_to(-length, 0)
        context.stroke_preserve()
        context.set_source_rgba(0, 0, 0, 0.5)
        context.stroke_preserve()
        context.restore()

    def show_result(self, widget, context, text, bg_rgba):
        '''Show final pass or fail result for the test
        '''

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
        x, y, width, height = context.text_extents(text)[:4]
        context.move_to(0.5 - (width / 2) - x, 0.5 - (height / 2) - y)
        context.show_text(text)
        context.restore()

    def start_countdown(self, duration):
        self._deadline = int(time.time()) + duration

    def show_countdown(self, widget, context, size):
        '''Show timeout countdown for test at hand
        '''
        width, height = widget.get_size_request()
        context.save()
        # place text lower right corner
        context.translate(width - (size*2), height)
        context.set_source_rgb(1, 0, 0)
        context.select_font_face(
            'Courier New', cairo.FONT_SLANT_NORMAL,
            cairo.FONT_WEIGHT_BOLD)

        context.set_font_size(size)
        x_bearing, y_bearing = context.text_extents('000')[:2]
        context.move_to(x_bearing, y_bearing)
        countdown = self._deadline - int(time.time())
        text = '%2d' % countdown
        context.show_text(text)
        context.restore()

    def request_action(self, widget, context, name):
        '''Determine action required by gpio state and show
        '''

        gpio_default = self.gpios.table[name][1]
        gpio_state = self.gpios.table[name][2]
        gpio_val = self.gpios.gpio_read(name)
        
        # state transitions based on current value
        if (gpio_state == 2) and (gpio_val != gpio_default):
            gpio_state-=1
            # refresh countdown
            self.start_countdown(self.timeout)
        elif (gpio_state == 1) and (gpio_val == gpio_default):
            gpio_state-=1
            self._successful.add(name)
            if self.gpio_info.__len__() is self._successful.__len__():
                self._success = True
                self.start_countdown(self.pass_msg_timeout)

        # store state change
        self.gpios.table[name][2] = gpio_state

        widget_width, widget_height = widget.get_size_request()
        context.save()
        ginfo = self.gpio_info[name]

        context.set_source_rgba(0, 0, 0, 1)
        
        if (ginfo['type'] == 'button'):
            text = ['Done', 'Release', 'Press']
            context.arc(ginfo['cx'], ginfo['cy'], ginfo['size'], 
                        0, math.radians(360))
            context.stroke()
            context.arc(ginfo['cx'], ginfo['cy'], ginfo['size'], 
                        0, math.radians(360))
        elif (ginfo['type'] == 'switch'):
            text = ['Done', 'Restore', 'Move']
            # two rects one outline of switch body the other
            # representing the position
            rect_x = ginfo['cx'] - ginfo['size']
            rect_y = ginfo['cy'] - ginfo['size'] / 2.0
            context.rectangle(rect_x, rect_y, ginfo['size'] * 2,
                              ginfo['size'])

            context.stroke()

            if gpio_state == 1:
                rect_x = rect_x + ginfo['size']
            context.rectangle(rect_x, rect_y, ginfo['size'],
                              ginfo['size'])
        else:
            raise

        context.set_source_rgba(*self.rgba_state[gpio_state])
        context.fill()
        
        if ginfo['arrow'] is not None:
            arrow_x = ginfo['arrow']['x']
            arrow_y = ginfo['arrow']['y']
            arrow_l = ginfo['arrow']['length']
            arrow_w = ginfo['arrow']['width']

            arrow_dir = ginfo['arrow']['direction']
            if (gpio_state == 1) and (ginfo['type'] == 'switch'):
                arrow_dir =+ 180

            self.show_arrow(context, ginfo['cx'], ginfo['cy'],
                            arrow_x, arrow_y, arrow_w, arrow_l, arrow_dir)

        context.scale(widget_width / 1.0, widget_height / 1.0)
        context.set_source_rgba(0.1, 0.1, 0.1, 0.95)
        context.select_font_face(
            'Verdana', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(.05)

        if gpio_state > 0:
            dtext = "%s %s %s now" % (text[gpio_state], name, ginfo['type'])
        else:
            dtext = "%s with %s %s" % (text[gpio_state], name, ginfo['type'])

        x_bearing, y_bearing, width, height = context.text_extents(dtext)[:4]
        context.move_to(0.5 - (width / 2) - x_bearing,
                        0.5 - (height / 2) - y_bearing)
        context.show_text(dtext)
        context.restore()

    def dump_coord(self, widget, event):
        x, y, state = event.window.get_pointer()
        print "(x,y) = (%d, %d)" % (x,y)
        return False

    def expose_event(self, widget, event):
        context = widget.window.cairo_create()

        context.set_source_surface(self._devrec_image, 0, 0)
        context.paint()

        if self._success is None:
            for key in self.gpio_info:
                if key not in self._successful:
                    self.request_action(widget, context, key)
                    break
                if self._deadline:
                    self.show_countdown(widget, context, 40)
        elif self._success:
            self.show_result(widget, context, 'PASS',
                             self.bg_rgba_pass)
        else:
            self.show_result(widget, context, 'FAIL',
                             self.bg_rgba_fail)
        return False

    def bogus_chg_gpio(self, window):
        self.gpios._gpio = not self.gpios._gpio
        window.queue_draw()
        return True

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

class devrec_gpio:
    '''
    Borrowed from site_tests/hardware_GPIOSwitches.  Will replace
    iotools implementation with successor chromium-os issue id=3119
    '''

    def __init__(self):
        self.gpio_read = None
        self.table = None
        self._gpio = 1

    def cfg(self):
        self.sku_table = {
            # SKU: gpio_read, recovery GPIO, developer mode,
            # firmware writeprotect
            'atom-proto': {'gpio_read': self.pinetrail_gpio_read,
                           # name : [<bit>, <type>, <default>,
                           # <assert>, <state>]
                           # <type> == button || switch || ro (read-only)
                           # <default> == 0 || 1
                           # <state> == number counts down 0
                           'developer': [7, 1, 2],
                           
                           'recovery': [6, 1, 2], 
                           },
            'unknown': {'gpio_read': self.bogus_gpio_read,
                        'developer': [7, 1, 2],
                        'recovery': [6, 1, 2],
                        },
            }

        # TODO(nsanders): Detect actual system type here by HWQual ID (?)
        # and redirect to the correct check.
        # We're just checking for any Atom here, and hoping for the best.
        if not os.system('cat /proc/cpuinfo | grep "model name" | '
                         'grep -qe "N4[0-9][0-9]"'):
            systemsku = 'atom-proto'
        else:
            systemsku = 'unknown'

        # Look up hardware configuration.
        if systemsku in self.sku_table:
            table = self.sku_table[systemsku]
            self.table = table
            self.gpio_read = table['gpio_read']
        else:
            raise KeyError('System settings not defined for board %s' %
                           systemsku)


    def bogus_gpio_read(self, name):
        return self._gpio
    
    def pinetrail_gpio_read(self, name):
        if not self.table.__contains__(name):
            raise

        # TODO(tbroch) hardcode for now ... iotools usages going away
        # longer term anyways
        path = '/home/autotest/deps/iotools/'
        # Generate symlinks for iotools.
        if not os.path.exists(path + 'pci_read32'):
            os.system(path + 'iotools --make-links')

        # Tigerpoint LPC Interface.
        tp_device = (0, 31, 0)
        # TP io port location of GPIO registers.
        tp_GPIOBASE = 0x48
        # IO offset to check GPIO levels.
        tp_GP_LVL_off = 0xc

        try:
            tp_gpio_iobase_str = os.popen(path + 'pci_read32 %s %s %s %s' % (
                    tp_device[0], tp_device[1], tp_device[2],  
                    tp_GPIOBASE)).readlines()[0]
        except:
            raise

        # Bottom bit of GPIOBASE is a flag indicating io space.
        tp_gpio_iobase = long(tp_gpio_iobase_str, 16) & ~1

        try:
            tp_gpio_mask_str = os.popen(path + 'io_read32 %s' % (
                    tp_gpio_iobase + tp_GP_LVL_off)).readlines()[0]
        except:
            raise

        tp_gpio_mask = long(tp_gpio_mask_str, 16)
        
        gpio_val = int((tp_gpio_mask >> self.table[name][0]) & 1)
        return gpio_val

def main():
    window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    window.set_name ('GPIO Test')
    window.connect('destroy', gtk.main_quit)
    window.connect( "delete-event", gtk.main_quit )

    bg_color = gtk.gdk.color_parse('midnight blue')
    window.modify_bg(gtk.STATE_NORMAL, bg_color)

    devrec_image = cairo.ImageSurface.create_from_png('devrec.png')
    devrec_image_size = (devrec_image.get_width(), devrec_image.get_height())

    drawing_area = gtk.DrawingArea()
    drawing_area.set_size_request(*devrec_image_size)
    
    exit_on_error = False
    test_setup = False
    if '--test_setup' in sys.argv:
        test_setup = True
    if '--exit-on-error' in sys.argv:
        exit_on_error = True

    drt = DevRecTest(devrec_image, exit_on_error=exit_on_error)

    screen = window.get_screen()
    screen_size = (screen.get_width(), screen.get_height())
    window.set_default_size(*screen_size)

    # used to locate btn/switches w/ respect to bg image
    if test_setup:
        drawing_area.connect('button_press_event', drt.dump_coord)
    else:
        gobject.timeout_add(100, drt.timer_event, window)
        gobject.timeout_add(2000, drt.bogus_chg_gpio, window)
        drt.start_countdown(drt.timeout)
    
    drawing_area.connect('expose_event', drt.expose_event)

    drawing_area.show()

    align = gtk.Alignment(xalign=0.5, yalign=0.5)
    align.add(drawing_area)
    align.show()

    drawing_area.set_events(gtk.gdk.EXPOSURE_MASK |
                            gtk.gdk.BUTTON1_MASK)

    window.add(align)
    window.show()

    gtk.main()

    return not drt._success

if __name__ == '__main__':
    main()
