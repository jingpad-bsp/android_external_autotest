# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This factory test allows execution of a test-based script, with the
# stdout of the script displayed in a the testing widget via gtk
# label.  Keyboard input will be passed to the script via its stdin.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import factory_test

import gobject
import gtk
import pango
import sys
import subprocess


class Script:

    def __init__(self, cmdline, label):
        self._cmdline
        self._label = label
        self._proc = subprocess.Popen(cmdline.split(),
                                      stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE)
        gobject.io_add_watch(self._proc.stdout, gobject.IO_IN, self.recv)

    def recv(self, src, cond):
        msg = self._proc.stdout.read()
        self._label.set_text(msg)
        self._label.queue_draw()
        returncode = self._proc.poll()
        if returncode is not None:
            gtk.main_quit()
            if returncode is not 0:
                error.TestFail('%s script returned %d' %
                               (self._cmdline, returncode))
        return True

    def send(self, msg):
        print >> self._proc.stdin, msg
        self._proc.stdin.flush()

    def quit(self):
        if self._proc.poll() is None:
            return
        factory_test.XXX('killing Script')
        self._proc.kill()


class factory_ScriptWrapper(test.test):
    version = 1

    def key_release_callback(self, widget, event):
        char = event.keyval in range(32,127) and chr(event.keyval) or None
        factory_test.XXX_log('key_release_callback %s(%s)' %
                             (event.keyval, char))
        if not factory_test.test_switch_on_trigger(event):
            self._script.send(char)
        return True

    def register_callbacks(self, window):
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gtk.gdk.KEY_RELEASE_MASK)

    def run_once(self, test_widget_size=None, trigger_set=None,
                 result_file_path=None, cmdline=None):

        factory_test.XXX_log('factory_ScriptWrapper')

        factory_test.init(trigger_set=trigger_set,
                          result_file_path=result_file_path)

        label = gtk.Label('')
        label.modify_font(pango.FontDescription('courier new condensed 16'))
        label.set_alignment(0.5, 0.5)
        label.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse('light green'))

        test_widget = gtk.EventBox()
        test_widget.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))
        test_widget.add(label)

        self._script = Script(cmdline, label)

        factory_test.run_test_widget(
            test_widget=test_widget,
            test_widget_size=test_widget_size,
            window_registration_callback=self.register_callbacks,
            cleanup_callback=self._script.quit)

        factory_test.XXX_log('exiting factory_ScriptWrapper')
