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
import logging
import os
import socket
import sys

import gobject
import gtk
import pango

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory_setup_modules
from cros.factory.test import factory
from cros.factory.test import shopfloor
from cros.factory.test import task
from cros.factory.test import ui
from cros.factory.test.event import Event, EventClient
from cros.factory.event_log import EventLog


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

_MSG_NO_SHOP_FLOOR_SERVER_URL = (
        'No shop floor server URL. Auto-testing stopped.\n\n'
        'Please install the factory test image using the mini-Omaha server\n'
        'rather than booting from a USB drive.\n\n'
        'For debugging or development, use the listed hot-keys to start\n'
        'individual tests.\n\n'
        '未指定 Shop Floor 伺服器位址，停止自動測試。\n\n'
        '請使用完整的 mini-Omaha 伺服器安裝測試程式，\n'
        '不要直接從 USB 碟開機執行。\n\n'
        '若想除錯或執行部份測試，請直接按下對應熱鍵。')

_LABEL_FONT = pango.FontDescription('courier new condensed 24')


class PressSpaceTask(task.FactoryTask):

    def start(self):
        self.add_widget(
                ui.make_label(_MSG_TASK_SPACE, font=ui.LABEL_LARGE_FONT))
        self.connect_window('key-press-event', self.window_key_press)

    def window_key_press(self, window, event):
        if event.keyval == gtk.keysyms.space:
            self.stop()
        else:
            factory.log('PressSpaceTask: non-space hit: %d' % event.keyval)
        return True


class ExternalPowerTask(task.FactoryTask):

    AC_CONNECTED = 1
    AC_DISCONNECTED = 2
    AC_CHECK_PERIOD = 500

    def start(self):
        self.active = True
        widget = ui.make_label(_MSG_TASK_POWER, font=ui.LABEL_LARGE_FONT)
        self.add_widget(widget)
        self.add_timeout(self.AC_CHECK_PERIOD, self.check_event, widget)

    def stop(self):
        self.active = False

    def check_event(self, label):
        if not self.active:
            return True
        state = self.get_external_power_state()
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


class ShopFloorTask(task.FactoryTask):
    def __init__(self, server_url):
        self.server_url = server_url or shopfloor.detect_default_server_url()

    def start(self):
        # Many developers will try to run factory test image directly without
        # mini-omaha server, so we should either alert and fail, or ask for
        # server address.
        if not self.server_url:
            self.add_widget(ui.make_label(_MSG_NO_SHOP_FLOOR_SERVER_URL,
                                          fg=ui.RED))
            return

        shopfloor.set_server_url(self.server_url)
        self.add_widget(ui.make_input_window(
                prompt=_MSG_TASK_SERIAL,
                on_validate=self.validate_serial_number,
                on_complete=self.complete_serial_task))

    def validate_serial_number(self, serial):
        # This is a callback function for widgets created by make_input_window.
        # When the input is not valid (or temporary network failure), either
        # return False or raise a ValueError with message to be displayed in
        # bottom status line of input window.
        try:
            # All exceptions
            shopfloor.check_serial_number(serial.strip())
            return True
        except shopfloor.ServerFault as e:
            raise ui.InputError("Server error:\n%s" % e)
        except ValueError as e:
            logging.exception("ValueError:")
            raise ui.InputError(e.message)
        except socket.gaierror as e:
            raise ui.InputError("Network failure (address error).")
        except socket.error as e:
            raise ui.InputError("Network failure:\n%s" % e[1])
        except:
            logging.exception("UnknownException:")
            raise ui.InputError(sys.exc_info()[1])
        return False

    def complete_serial_task(self, serial):
        serial = serial.strip()
        EventLog.ForAutoTest().Log('mlb_serial_number',
                                   serial_number=serial)
        factory.log('Serial number: %s' % serial)
        shopfloor.set_serial_number(serial)

        EventClient().post_event(Event(Event.Type.UPDATE_SYSTEM_INFO))
        self.stop()
        return True


class factory_Start(test.test):
    version = 2

    def run_once(self,
                 press_to_continue=True,
                 require_external_power=False,
                 require_shop_floor=None,
                 shop_floor_server_url=None):
        factory.log('%s run_once' % self.__class__)

        self._task_list = []

        # Reset shop floor data only if require_shop_floor is explicitly
        # defined, for test lists using factory_Start multiple times between
        # groups (ex, to prompt for space or check power adapter).
        if require_shop_floor is not None:
            shopfloor.reset()
            shopfloor.set_enabled(require_shop_floor)

        if require_shop_floor:
            self._task_list.append(ShopFloorTask(shop_floor_server_url))
        if require_external_power:
            self._task_list.append(ExternalPowerTask())
        if press_to_continue:
            self._task_list.append(PressSpaceTask())

        if self._task_list:
            task.run_factory_tasks(self.job, self._task_list)

        factory.log('%s run_once finished' % repr(self.__class__))
