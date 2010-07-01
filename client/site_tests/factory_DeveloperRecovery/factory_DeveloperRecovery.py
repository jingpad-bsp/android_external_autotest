# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# Intended for use during manufacturing to validate Developer mode
# switch and Recovery button function properly.  This program will
# display an image of the d-housing with Developer switch and Recovery
# button.  Operator will then be instructed via text and visually to
# switch and restore the Developer switch and press/release the
# Recovery button.  Success at each step resets a 20 second countdown timer.


import cairo
import gobject
import gtk
import sys
import time
import os
import math

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_test
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


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
                        'cy' : 425,
                        'size' : 30,
                        'arrow' : {'x' : 580,
                                   'y' : 425,
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

    def __init__(self, autodir, devrec_image):
        self._devrec_image = devrec_image
        self._successful = set()
        self._deadline = None
        self._success = None
        self.gpios = DevRecGpio(autodir)
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

    def start_countdown(self, duration):
        self._deadline = int(time.time()) + duration

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
            dtext = "%s %s %s now [ %d ] " % \
                (text[gpio_state], name, ginfo['type'],
                 (self._deadline - int(time.time())))
        else:
            dtext = "%s with %s %s" % (text[gpio_state], name, ginfo['type'])

        x_bearing, y_bearing, width, height = context.text_extents(dtext)[:4]
        context.move_to(0.5 - (width / 2) - x_bearing,
                        0.5 - (height / 2) - y_bearing)
        context.show_text(dtext)
        context.restore()
        return True

    def expose_event(self, widget, event):
        context = widget.window.cairo_create()

        context.set_source_surface(self._devrec_image, 0, 0)
        context.paint()

        if self._success is None:
            for key in self.gpio_info:
                if key not in self._successful:
                    self.request_action(widget, context, key)
                    break
        return True

    def timer_event(self, window):
        if not self._deadline:
            # Ignore timer events with no countdown in progress.
            return True
        if self._deadline <= time.time():
            self._deadline = None
            if self._success is None:
                self._success = False
            elif self._success:
                sys.exit(0)
        window.queue_draw()
        return True


class DevRecGpio:
    '''
    Borrowed from site_tests/hardware_GPIOSwitches.  Will replace
    iotools implementation with successor chromium-os issue id=3119
    '''

    def __init__(self, autodir):
        self._autodir = autodir
        self.gpio_read = None
        self.table = None

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

    def pinetrail_gpio_read(self, name):
        if not self.table.__contains__(name):
            raise

        # Tigerpoint LPC Interface.
        tp_device = (0, 31, 0)
        # TP io port location of GPIO registers.
        tp_GPIOBASE = 0x48
        # IO offset to check GPIO levels.
        tp_GP_LVL_off = 0xc

        try:
            tp_gpio_iobase_str = os.popen('pci_read32 %s %s %s %s' % (
                    tp_device[0], tp_device[1], tp_device[2],
                    tp_GPIOBASE)).readlines()[0]
        except:
            factory.log("ERROR: reading gpio iobase")


        # Bottom bit of GPIOBASE is a flag indicating io space.
        tp_gpio_iobase = long(tp_gpio_iobase_str, 16) & ~1

        try:
            tp_gpio_mask_str = os.popen('io_read32 %s' % (
                    tp_gpio_iobase + tp_GP_LVL_off)).readlines()[0]
        except:
            factory.log("ERROR: reading gpio value")

        tp_gpio_mask = long(tp_gpio_mask_str, 16)

        gpio_val = int((tp_gpio_mask >> self.table[name][0]) & 1)
        return gpio_val


class factory_DeveloperRecovery(test.test):
    version = 1
    preserve_srcdir = True

    def key_release_callback(self, widget, event):
        self._ft_state.exit_on_trigger(event)
        return True

    def register_callbacks(self, window):
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gtk.gdk.KEY_RELEASE_MASK)

    def run_once(self,
                 test_widget_size=None,
                 trigger_set=None,
                 result_file_path=None,
                 layout=None):

        factory.log('%s run_once' % self.__class__)

        self._ft_state = factory_test.State(
            trigger_set=trigger_set,
            result_file_path=result_file_path)

        os.chdir(self.srcdir)
        dr_image = cairo.ImageSurface.create_from_png('%s.png' % layout)
        image_size = (dr_image.get_width(), dr_image.get_height())

        test = DevRecTest(autodir, dr_image)

        drawing_area = gtk.DrawingArea()
        drawing_area.set_size_request(*image_size)
        drawing_area.connect('expose_event', test.expose_event)
        drawing_area.add_events(gtk.gdk.EXPOSURE_MASK)
        gobject.timeout_add(200, test.timer_event, drawing_area)

        test.start_countdown(test.timeout)

        self._ft_state.run_test_widget(
            test_widget=drawing_area,
            test_widget_size=test_widget_size,
            window_registration_callback=self.register_callbacks)

        factory.log('%s run_once finished' % self.__class__)
