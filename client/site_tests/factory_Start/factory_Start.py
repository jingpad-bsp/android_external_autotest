# -*- coding: utf-8 -*-
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# DESCRIPTION :
# This factory test is run a the start of a test sequence to verify the DUT has
# been setup correctly.
#
# It prompts and waits for a keypress (SPACE) to start testing.
# Pass 'press_to_continue' = False as a darg in the test_list to disable.
#
# It optionally prompts and waits for external power to be applied.
# Pass 'require_external_power' = False as a darg in the test_list to disable.

import glob
import gobject
import gtk
import os
import pango
import sys

from gtk import gdk

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

_LABEL_FONT = pango.FontDescription('courier new condensed 24')
_PLUG_IN_POWER_FMT_STR = \
    'Plug in external power to continue.\n插電才繼續.'
_SPACE_TO_START_FMT_STR = \
    'Hit SPACE to start testing...\n按 "空白鍵" 開始測試...'

class Adapter_State:
    CONNECTED = 1
    DISCONNECTED = 2

class factory_Start(test.test):
    version = 1

    def initialize(self):
        self._error = False
        self._error_message = 'An unspecified error occurred.'

    def set_error_and_quit(self, message):
        self._error = True
        self._error_message = message
        gtk.main_quit()

    def key_release_callback(self, widget, event):
        char = event.keyval in range(32,127) and chr(event.keyval) or None
        factory.log('key_release %s(%s)' % (event.keyval, char))
        if event.keyval == ord(' '):
            if not self.require_external_power:
                gtk.main_quit()
            elif self.get_external_power_state() == Adapter_State.CONNECTED:
                gtk.main_quit()
        return True

    def register_callbacks(self, window):
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gdk.KEY_RELEASE_MASK)

    def get_external_power_state(self):
        for type_file in glob.glob('/sys/class/power_supply/*/type'):
            try:
                type = utils.read_one_line(type_file).strip()
            except IOError as details:
                self.set_error_and_quit('%s' % details)
            if type == 'Mains':
                status_file = os.path.join(
                        os.path.dirname(type_file), 'online')
                try:
                    status = int(utils.read_one_line(status_file).strip())
                except ValueError as details:
                    self.set_error_and_quit(
                            'Invalid external power state in %s: %s' %
                            (status_file, details))
                except IOError as details:
                    self.set_error_and_quit('%s' % details)
                if status == 0:
                    return Adapter_State.DISCONNECTED
                elif status == 1:
                    return Adapter_State.CONNECTED
                else:
                    self.set_error_and_quit(
                            'Invalid external power state "%s" in %s.' %
                            (status, status_file))
        self.set_error_and_quit('Unable to determine external power state.')

    def external_power_event(self, label):
        if self.get_external_power_state() == Adapter_State.DISCONNECTED:
            label.modify_fg(gtk.STATE_NORMAL, ful.LABEL_COLORS[ful.ACTIVE])
            label.set_label(_PLUG_IN_POWER_FMT_STR)
        elif not self.press_to_continue:
            gtk.main_quit()
        else:
            label.modify_fg(gtk.STATE_NORMAL, ful.LABEL_COLORS[ful.PASSED])
            label.set_label(_SPACE_TO_START_FMT_STR)
        gtk.main_iteration(False)
        return True

    def run_once(self, press_to_continue=True, require_external_power=False):
        factory.log('%s run_once' % self.__class__)

        self.press_to_continue = press_to_continue
        self.require_external_power = require_external_power

        label = ful.make_label('', font=_LABEL_FONT)
        test_widget = gtk.EventBox()
        test_widget.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        test_widget.add(label)

        if self.require_external_power:
                gobject.timeout_add(500, self.external_power_event, label)

        if self.press_to_continue and not self.require_external_power:
            label.set_label(_SPACE_TO_START_FMT_STR)

        if self.require_external_power or self.press_to_continue:
            ful.run_test_widget(
                    self.job, test_widget,
                    window_registration_callback=self.register_callbacks)

        if self._error:
            raise error.TestError(self._error_message)

        factory.log('%s run_once finished' % repr(self.__class__))
