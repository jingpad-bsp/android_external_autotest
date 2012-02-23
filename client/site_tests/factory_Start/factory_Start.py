# -*- coding: utf-8 -*-
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# DESCRIPTION :
# This factory test runs at the start of a test sequence to verify the DUT has
# been setup correctly.
#
# The start provides several settings (set via darg):
# 'require_external_power': Prompts and waits for external power to be applied.
# 'require_shop_floor': Prompts and waits for serial number as input.  The
#       server is default to the host running mini-omaha, unless you specify an
#       URL by 'shop_floor_server_url' darg.
# 'press_to_continue': Prompts and waits for a key press (SPACE) to continue.

import glob
import os
import sys

import gobject
import gtk
import pango
from gtk import gdk

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import ui as ful
from autotest_lib.client.cros.factory import shopfloor


# Messages for tasks
_MSG_TASK_POWER = (
        'Plug in external power to continue.\n'
        '請插上外接電源以繼續。')
_MSG_TASK_SERIAL = (
        'Enter valid serial number:\n'
        '請輸入有效的序號:')
_MSG_TASK_SPACE = (
        'Hit SPACE to start testing...\n'
        '按 "空白鍵" 開始測試...')
_LABEL_FONT = pango.FontDescription('courier new condensed 24')


class Task(object):
    def __init__(self, ui):
        self._ui = ui

    def start(self):
        """Initializes task and returns a widget for display, if available."""
        return None

    def stop(self):
        """Notifies the test backend current task is finished."""
        return self._ui.stop_task(self)

    def get_window(self):
        """Returns UI top level window."""
        return self._ui.get_window()

    def set_error_and_quit(self, message):
        """Sets error message and requests for quiting entire test."""
        return self._ui.set_error_and_quit(message)


class PressSpaceTask(Task):
    def start(self):
        window = self._ui.get_window()
        window.add_events(gdk.KEY_PRESS_MASK)
        self.callback = (window, window.connect('key-press-event',
                                                self.check_space))
        return ful.make_label(_MSG_TASK_SPACE, font=ful.LABEL_LARGE_FONT)

    def stop(self):
        (window, callback_id) = self.callback
        window.disconnect(callback_id)
        Task.stop(self)

    def check_space(self, window, event):
        if event.keyval == gtk.keysyms.space:
            self.stop()
        else:
            factory.log('PressSpaceTask: non-space hit: %d' % event.keyval)
        return True


class ExternalPowerTask(Task):

    AC_CONNECTED = 1
    AC_DISCONNECTED = 2
    AC_CHECK_PERIOD = 500

    def start(self):
        widget = ful.make_label(_MSG_TASK_POWER, font=ful.LABEL_LARGE_FONT)
        self._timeout = gobject.timeout_add(self.AC_CHECK_PERIOD,
                                            self.check_event, widget)
        self._active = True
        return widget

    def stop(self):
        self._active = False
        gobject.source_remove(self._timeout)
        Task.stop(self)

    def check_event(self, label):
        if not self._active:
            return True
        try:
            state = self.get_external_power_state()
        except (IOError, ValueError) as details:
            self.set_error_and_quit('ExternalPowerTask: %s' % details)
        except:
            self.set_error_and_quit('ExternalPowerTask: Unknown exception: %s' %
                                    sys.exc_info()[0])
        else:
            if state == self.AC_CONNECTED:
                self.stop()
        return True

    def get_external_power_state(self):
        for type_file in glob.glob('/sys/class/power_supply/*/type'):
            type_value = utils.read_one_line(type_file).strip()
            if type_value == 'Mains':
                status_file = os.path.join(os.path.dirname(type_file), 'online')
                try:
                    status = int(utils.read_one_line(status_file).strip())
                except ValueError as details:
                    raise ValueError('Invalid external power state in %s: %s' %
                                     (status_file, details))
                if status == 0:
                    return self.AC_DISCONNECTED
                elif status == 1:
                    return self.AC_CONNECTED
                else:
                    raise ValueError('Invalid external power state "%s" in %s' %
                                     (status, status_file))
        raise IOError('Unable to determine external power state.')


class ShopFloorTask(Task):
    def __init__(self, ui, server_url):
        Task.__init__(self, ui)
        self.server_url = server_url or shopfloor.detect_default_server_url()
        shopfloor.set_server_url(self.server_url)

    def start(self):
        return ful.make_input_window(
                prompt=_MSG_TASK_SERIAL,
                on_validate=self.validate_serial_number,
                on_complete=self.complete_serial_task)

    def validate_serial_number(self, serial):
        try:
            shopfloor.check_serial_number(serial.strip())
            return True
        except shopfloor.Fault as e:
            factory.log("Server Error: %s" % e)
        except:
            factory.log("Unknown exception: %s" % repr(sys.exc_info()))
        return False

    def complete_serial_task(self, serial):
        serial = serial.strip()
        factory.log('Serial number: %s' % serial)
        shopfloor.set_serial_number(serial)
        self.stop()
        return True


class factory_Start(test.test):
    version = 2

    def set_error_and_quit(self, message):
        self._error = True
        self._error_message = message
        gtk.main_quit()

    def get_window(self):
        return self._window

    def stop_task(self, task):
        # Remove all active widgets and registered callbacks
        factory.log('factory_Start: Stopping task: %s' %
                    task.__class__.__name__)
        for widget in self._test_widget.get_children():
            self._test_widget.remove(widget)
        self._task_list.remove(task)
        self.find_next_task()

    def find_next_task(self):
        if self._task_list:
            task = self._task_list[0]
            factory.log('factory_Start: Starting task: %s' %
                        task.__class__.__name__)
            self._test_widget.add(task.start())
            self._test_widget.show_all()
        else:
            gtk.main_quit()

    def register_window(self, window):
        """Registers top-level window for tasks."""
        self._window = window
        self.find_next_task()
        return True

    def run_once(self,
                 press_to_continue=True,
                 require_external_power=False,
                 require_shop_floor=False,
                 shop_floor_server_url=None):
        factory.log('%s run_once' % self.__class__)

        self._error = False
        self._error_message = 'An unspecified error occurred.'

        self._task_list = []
        shopfloor.reset()
        shopfloor.set_enabled(require_shop_floor)
        if require_shop_floor:
            self._task_list.append(ShopFloorTask(self, shop_floor_server_url))
        if require_external_power:
            self._task_list.append(ExternalPowerTask(self))
        if press_to_continue:
            self._task_list.append(PressSpaceTask(self))

        if self._task_list:
            # Creates user interface.
            self._test_widget = gtk.VBox()
            ful.run_test_widget(
                    self.job, self._test_widget,
                    window_registration_callback=self.register_window)

        if self._error:
            raise error.TestError(self._error_message)

        factory.log('%s run_once finished' % repr(self.__class__))
