# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This factory test allows execution of a test-based script, with the
# stdout of the script displayed in a the testing widget via gtk
# label.  Keyboard input will be passed to the script via its stdin.

import imp
import gobject
import gtk
import pango
import sys
import subprocess

from gtk import gdk

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import pexpect


_MAX_LABEL_CHARS=256


class Script:

    def __init__(self, cmdline, pexpect, label):
        self._cmdline = cmdline
        self._label = label
        self._ibuf = ''
        self._proc = pexpect.spawn(cmdline)
        gobject.io_add_watch(self._proc.fileno(), gobject.IO_IN, self.recv)

    def recv(self, src, cond):
        msg = self._proc.read_nonblocking(_MAX_LABEL_CHARS)
        factory.log('recv script msg %s' % repr(msg))
        self._label.set_text(msg)
        self._label.queue_draw()
        if not self._proc.isalive():
            self._proc.close()
            gtk.main_quit()
            if self._proc.exitstatus is not 0:
                error.TestFail('%s script return code was %d' %
                               (self._cmdline, self._proc.exitstatus))
        return True

    def send(self, char):
        if char != '\n':
            self._ibuf += char
            return
        factory.log('sending script %s' % repr(self._ibuf))
        self._proc.sendline(self._ibuf)
        self._ibuf = ''


class factory_ScriptWrapper(test.test):
    version = 1

    def key_release_callback(self, widget, event):
        char = event.keyval in range(32,127) and chr(event.keyval) or None
        char = event.keyval == gdk.keyval_from_name('Return') and '\n' or char
        if not self._ft_state.exit_on_trigger(event) and char is not None:
            self._script.send(char)
        return True

    def register_callbacks(self, window):
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gtk.gdk.KEY_RELEASE_MASK)

    def run_once(self,
                 test_widget_size=None,
                 trigger_set=None,
                 result_file_path=None,
                 cmdline=None):

        factory.log('%s run_once' % self.__class__)

        self._ft_state = ful.State(
            trigger_set=trigger_set,
            result_file_path=result_file_path)

        label = gtk.Label('')
        label.modify_font(pango.FontDescription('courier new condensed 16'))
        label.set_alignment(0.5, 0.5)
        label.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse('light green'))

        test_widget = gtk.EventBox()
        test_widget.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))
        test_widget.add(label)

        self._script = Script(cmdline, pexpect, label)

        self._ft_state.run_test_widget(
            test_widget=test_widget,
            test_widget_size=test_widget_size,
            window_registration_callback=self.register_callbacks)

        factory.log('%s run_once finished' % self.__class__)
