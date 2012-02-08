# -*- coding: utf-8 -*-
#
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

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils

from autotest_lib.client.cros import gpio
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import ui as ful

class DevRecTest(object):
    gpio_info = {
        # Note, names are NOT arbitrary.  Will need to change gpio_setup before
        # modifying
        'developer_switch' : {'type' : 'switch',
                              'cx' : 475,
                              'cy' : 375,
                              'size' : 30,
                              'arrow' : {'x' : 425,
                                         'y' : 375,
                                         'width' : 15,
                                         'length' : 100,
                                         # in degrees starts as rt arrow
                                         'direction' : 0,
                                         },
                              },
        'recovery_button' : {'type' : 'button',
                             'cx' : 475,
                             'cy' : 375,
                             'size' : 30,
                             'arrow' : {'x' : 420,
                                        'y' : 375,
                                        'width' : 15,
                                        'length' : 100,
                                        'direction' : 270,
                                        }
                             },
        }

    # How long DevRecTest allows in seconds until failing
    timeout = 90
    # How long to display the success message in seconds before exit.
    pass_msg_timeout = 2

    # Background color and alpha for various states
    rgba_state = [(0.0, 1.0, 0.0, 0.9),
                  (0.9, 0.9, 0.0, 0.6),
                  (0.9, 0.0, 0.0, 0.6)]

    def __init__(self, devrec_image, gpio):
        self._devrec_image = devrec_image
        self._successful = set()
        self._deadline = None
        self._success = None
        self._error_message = 'Test was unsuccessful'
        self.gpios = DevRecGpio(gpio)

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

        gpio_default = self.gpios.gpio_default(name)
        gpio_state = self.gpios.gpio_state(name)
        gpio_val = self.gpios.gpio_read(name)

        # state transitions based on current value
        if (gpio_state == 2) and (gpio_val != gpio_default):
            gpio_state-=1
            # refresh countdown
            self.start_countdown(self.timeout)
        elif (gpio_state == 1) and (gpio_val == gpio_default):
            gpio_state-=1
            self._successful.add(name)

        # store state change
        self.gpios.table[name][1] = gpio_state

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

        if gpio_state > 0 and self._deadline:
            dtext = "%s %s now [ %d ]" % \
                (text[gpio_state], name, (self._deadline - int(time.time())))
        else:
            dtext = "%s with %s" % (text[gpio_state], name)

        x_bearing, y_bearing, width, height = context.text_extents(dtext)[:4]
        context.move_to(0.5 - (width / 2) - x_bearing,
                        0.5 - (height / 2) - y_bearing)
        context.show_text(dtext)

        dtext = "Press Q to fail."
        x_bearing, y_bearing, width, height = context.text_extents(dtext)[:4]
        context.move_to(0.08 - x_bearing,
                        0.9 - (height / 2) - y_bearing)
        context.show_text(dtext)

        context.restore()
        return True

    def time_expired(self):
        if self._deadline is None:
            return None
        if self._deadline is not None and self._deadline <= time.time():
            return True
        else:
            return False

    def expose_event(self, widget, event):
        context = widget.window.cairo_create()

        context.set_source_surface(self._devrec_image, 0, 0)
        context.paint()

        if self.time_expired() or self.gpios.cur_gpio() in self._successful:
            self.gpios.next_gpio()
            self.start_countdown(self.timeout)

        if self.gpios.cur_gpio():
            self.request_action(widget, context, self.gpios.cur_gpio())
        elif self.gpios.num_gpios == len(self._successful):
            self._success = True

        return True

    def timer_event(self, window):
        if self._success:
            gtk.main_quit()
        if not self._deadline:
            # Ignore timer events with no countdown in progress.
            return True
        if self.time_expired():
            if self._success is None:
                self._success = False
                self._error_message = ('Timeout occured before test pass ' +
                    '(%s)' % self.gpios.cur_gpio())
                gtk.main_quit()

        window.queue_draw()
        return True

    def key_release_callback(self, widget, event):
        if event.keyval == ord('Q') or event.keyval == ord('q'):
            self._success = False
            self._error_message = ('User exited before test pass ' +
                '(%s)' % self.gpios.cur_gpio())
            gtk.main_quit()

        return True

    def register_callbacks(self, window):
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gtk.gdk.KEY_RELEASE_MASK)


class DevRecGpio:
    '''
    Borrowed from site_tests/hardware_GPIOSwitches.
    '''

    def __init__(self, gpio):
        self._gpio = gpio
        self._cur_gpio = None
        self._gpio_list = []
        self.table = None
        self.cfg()

    def cfg(self):
        # The GPIO values should be interpreted by kernel driver so gpio_read
        # is always returning "logical" values. For example, developer_switch
        # should always be "0" for "disabled" and "1" for "enabled", no matter
        # whether the real PCB is made pull-high or pull-low.
        self.table = {
            # name : [<default>, <state>]
            # <default> == 0 || 1
            # <state> == number counts down 0
            'developer_switch': [1, 2],
            'recovery_button': [0, 2],
        }

        self._gpio_list = self.table.keys()
        self._gpio_list.reverse()
        self.num_gpios = len(self._gpio_list)

    def gpio_read(self, name):
        if name not in self.table:
            raise error.TestNAError(
                    'Unable to locate definition for gpio %s\n'
                    '測試程式找不到 gpio %s' % (name, name))
        try:
            return self._gpio.read(name)
        except:
            raise error.TestError(
                    'Unable to read gpio value "%s"\n'
                    '測試程式無法讀取 gpio 數值 "%s"' % (name, name))

    def cur_gpio(self):
        if self._cur_gpio is None:
            self._cur_gpio = self.next_gpio()
        return self._cur_gpio

    def next_gpio(self):
        if len(self._gpio_list):
            self._cur_gpio = self._gpio_list.pop()
        else:
            self._cur_gpio = False
        return self.cur_gpio()

    def gpio_default(self, name):
        return self.table[name][0]

    def gpio_state(self, name):
        return self.table[name][1]


class factory_DeveloperRecovery(test.test):
    version = 2
    preserve_srcdir = True

    def initialize(self):
        self._gpio = gpio.Gpio(error.TestError)
        self._gpio.setup()

    def run_once(self, layout=None):

        factory.log('%s run_once' % self.__class__)

        os.chdir(self.srcdir)
        dr_image = cairo.ImageSurface.create_from_png('%s.png' % layout)
        image_size = (dr_image.get_width(), dr_image.get_height())

        test = DevRecTest(dr_image, self._gpio)

        drawing_area = gtk.DrawingArea()
        drawing_area.set_size_request(*image_size)
        drawing_area.connect('expose_event', test.expose_event)
        drawing_area.add_events(gtk.gdk.EXPOSURE_MASK)
        gobject.timeout_add(200, test.timer_event, drawing_area)

        test.start_countdown(test.timeout)

        ful.run_test_widget(self.job, drawing_area,
            window_registration_callback=test.register_callbacks)

        if not test._success:
            raise error.TestFail(test._error_message)

        factory.log('%s run_once finished' % self.__class__)
