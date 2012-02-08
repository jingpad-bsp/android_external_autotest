# -*- coding: utf-8 -*-
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# DESCRIPTION :
#
# This is a factory test for the audio function. An external loopback dongle
# is required to automatically capture and detect the playback tones.

import gtk
import os
import re
import threading
import utils

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import ui as ful

_LABEL_START_STR = 'Hit s to start loopback test\n' +\
        '按s鍵開始音源回放測試\n\n'
_LABEL_IN_PROGRESS_STR = 'Loopback testing...\n' +\
        '音源回放測試中...\n\n'

class factory_AudioLoop(test.test):
    version = 1

    def key_press_callback(self, widget, event):
        if event.keyval == ord('s'):
            self._main_widget.remove(self._loop_status_label)
            self._loop_status_label = None
            self._loop_status_label = ful.make_label(_LABEL_IN_PROGRESS_STR,
                                                    fg = ful.WHITE)
            self._main_widget.add(self._loop_status_label)
            self._main_widget.show_all()
            self._main_widget.queue_draw()
            return True

    def key_release_callback(self, widget, event):
        if event.keyval == ord('s'):
            self._result = self.job.run_test(
                    'audiovideo_LineOutToMicInLoopback',
                    tag=self._subtest_tag)
            gtk.main_quit()
            return True

    def register_callbacks(self, window):
        window.connect('key-press-event', self.key_press_callback)
        window.add_events(gtk.gdk.KEY_PRESS_MASK)
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gtk.gdk.KEY_RELEASE_MASK)

    def run_once(self, subtest_tag=None):
        factory.log('%s run_once' % self.__class__)
        self._subtest_tag = subtest_tag

        self._main_widget = gtk.EventBox()
        self._main_widget.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        self._loop_status_label = ful.make_label(_LABEL_START_STR,
                                                fg = ful.WHITE)
        self._main_widget.add(self._loop_status_label)

        ful.run_test_widget(self.job, self._main_widget,
                window_registration_callback = self.register_callbacks)

        if not self._result:
            raise error.TestFail('ERROR: loopback test fail')
