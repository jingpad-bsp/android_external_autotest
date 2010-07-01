# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This is an example factory test that does not really do anything --
# it displays a message in the center of the testing area, as
# communicated by arguments to run_once().  This test makes use of the
# factory_test library to display its UI, and to monitor keyboard
# events for test-switching triggers.  This test can be terminated by
# typing SHIFT-Q.


import gobject
import gtk
import pango
import os
import sys

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_test
from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error


_STATE_WAIT_INSERT = 1
_STATE_WAIT_REMOVE = 2


def find_root_dev():
    rootdev = utils.system_output('rootdev')
    return os.path.basename(rootdev[:-1])


def find_all_storage_dev():
    lssys = utils.run('ls -d /sys/block/sd*')
    devices = lssys.stdout.rsplit('\n')
    new_devices = set(os.path.basename(d.rstrip()) for d in devices if d)
    return new_devices


class factory_ExternalStorage(test.test):
    version = 1

    def key_release_callback(self, widget, event):
        char = event.keyval in range(32,127) and chr(event.keyval) or None
        factory.log('key_release_callback %s(%s)' %
                             (event.keyval, char))
        self._ft_state.exit_on_trigger(event)
        return True

    def register_callbacks(self, window):
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gtk.gdk.KEY_RELEASE_MASK)

    def rescan_storage(self, test_tag):
        if self._state == _STATE_WAIT_INSERT:
            new_devices = find_all_storage_dev()
            diff = new_devices - self._devices
            if diff:
                self._devices = new_devices
                factory.log('found new devs : %s' % diff)
                self._target_device = diff.pop()
                devpath = '/dev/%s' % self._target_device
                self._prompt.set_test('testing drive %s...', devpath)
                gtk.main_iteration()
                test._result = self.job.run_test('hardware_StorageFio',
                                                 dev=devpath, tag=test_tag)
                self._prompt.set_test('remove USB drive...')
                self._state = _STATE_WAIT_REMOVE
        else:
            diff = self._devices - find_all_storage_dev()
            if diff:
                if diff != set(self._target_device):
                    raise error.TestFail('too many devs removed (%s vs %s)' %
                                         (diff, self._target_device))
                gtk.main_quit()
        return True

    def run_once(self, test_widget_size=None, trigger_set=None,
                 result_file_path=None, test_tag_prefix=None, test_count=None):

        factory.log('%s run_once' % self.__class__)

        test_tag = '%s_%s' % (test_tag_prefix, test_count)
        factory.log('test_tag = %s' % test_tag)

        self._ft_state = factory_test.State(
            trigger_set=trigger_set,
            result_file_path=result_file_path)

        label = gtk.Label('')
        label.modify_font(pango.FontDescription('courier new condensed 20'))
        label.set_alignment(0.5, 0.5)
        label.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse('light green'))
        self._prompt = label

        test_widget = gtk.EventBox()
        test_widget.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))
        test_widget.add(label)

        self._prompt.set_text('insert USB drive...')
        self._state = _STATE_WAIT_INSERT
        self._result = False
        self._devices = find_all_storage_dev()
        gobject.timeout_add(250, self.rescan_storage, test_tag)

        self._ft_state.run_test_widget(
            test_widget=test_widget,
            test_widget_size=test_widget_size,
            window_registration_callback=self.register_callbacks)

        factory.log('%s run_once finished' % self.__class__)
