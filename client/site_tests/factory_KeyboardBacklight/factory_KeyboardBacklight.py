# -*- coding: utf-8 -*-
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This is a factory test to test the keyboard backlight. Keyboard backlight will
# light up and operator will check if he/she can see the light. Then backlight
# will dim and operator will check if the light is off.


import gtk
import logging

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.cros import factory_setup_modules
from cros.factory.test import factory
from cros.factory.test import ui as ful


_LABEL_BIG_SIZE = (280, 60)
_LABEL_STATUS_SIZE = (140, 30)
_LABEL_START_STR = ('hit SPACE to start keyboard backlight test\n'
                    '按空白鍵開始各項鍵盤背光測試\n\n')
_SUBTEST_LIST = ['Light up', 'Dim']


class factory_KeyboardBacklight(test.test):
    version = 1

    def kblight_subtest_widget(self, name):
        vb = gtk.VBox()
        ebh = gtk.EventBox()
        ebh.modify_bg(gtk.STATE_NORMAL, ful.LABEL_COLORS[ful.ACTIVE])
        ebh.add(ful.make_label(name, size=_LABEL_BIG_SIZE,
                               fg=ful.BLACK))
        vb.pack_start(ebh)
        vb.pack_start(ful.make_vsep(3), False, False)
        if name == "Light up":
            lab_str = ('Check if keyboard backlight lights up.\n'
                       '請檢查鍵盤背光是否點亮\n')
        else:
            lab_str = ('Check if keyboard backlight turns off.\n'
                       '請檢查鍵盤背光是否熄滅\n')
        vb.pack_start(ful.make_label(lab_str, fg=ful.WHITE))
        vb.pack_start(ful.make_vsep(3), False, False)
        vb.pack_start(ful.make_label(ful.USER_PASS_FAIL_SELECT_STR,
                                     fg=ful.WHITE))

        # Need event box to effect bg color.
        eb = gtk.EventBox()
        eb.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        eb.add(vb)

        self._subtest_widget = eb

        self._test_widget.remove(self._top_level_test_list)
        self._test_widget.add(self._subtest_widget)
        self._test_widget.show_all()

    def goto_next_subtest(self):
        if not self._subtest_queue:
            gtk.main_quit()
            return
        self._current_subtest = self._subtest_queue.pop()
        name = self._current_subtest
        self.update_status(name, ful.ACTIVE)
        if name == "Light up":
                result = utils.system_output('ectool pwmsetkblight 100')
        else:
                result = utils.system_output('ectool pwmsetkblight 0')
        logging.info(result)

    def cleanup_subtest(self):
        self._test_widget.remove(self._subtest_widget)
        self._subtest_widget = None
        self._test_widget.add(self._top_level_test_list)
        self._test_widget.show_all()
        self.goto_next_subtest()

    def key_release_callback(self, widget, event):
        name = self._current_subtest
        # Make sure we capture more advanced key events only when
        # entered a subtest.
        if self._subtest_widget is None:
            if event.keyval == gtk.keysyms.space:
                # Start subtest.
                self.kblight_subtest_widget(name)
            return True
        if event.keyval == gtk.keysyms.Tab:
            self.update_status(name, ful.FAILED)
            self.cleanup_subtest()
        elif event.keyval == gtk.keysyms.Return:
            self.update_status(name, ful.PASSED)
            self.cleanup_subtest()
        elif event.keyval == ord('Q'):
            gtk.main_quit()
        self._test_widget.queue_draw()
        return True

    def update_status(self, name, status):
        self._status_map[name] = status
        self._label_status[name].set_text(status)
        self._label_status[name].modify_fg(gtk.STATE_NORMAL,
                                           ful.LABEL_COLORS[status])
        self._label_status[name].queue_draw()

    def make_subtest_label_box(self, name):
        eb = gtk.EventBox()
        eb.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        label_status = ful.make_label(ful.UNTESTED, size=_LABEL_STATUS_SIZE,
                                      alignment=(0, 0.5),
                                      fg=ful.LABEL_COLORS[ful.UNTESTED])
        self._label_status[name] = label_status
        label_en = ful.make_label(name, alignment=(1,0.5))
        label_sep = ful.make_label(' : ', alignment=(0.5, 0.5))
        hbox = gtk.HBox()
        hbox.pack_end(label_status, False, False)
        hbox.pack_end(label_sep, False, False)
        hbox.pack_end(label_en, False, False)
        eb.add(hbox)
        return eb

    def register_callbacks(self, window):
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gtk.gdk.KEY_RELEASE_MASK)

    def run_once(self):

        factory.log('%s run_once' % self.__class__)

        self._subtest_queue = [x for x in reversed(_SUBTEST_LIST)]
        self._status_map = dict((n, ful.UNTESTED) for n in _SUBTEST_LIST)
        self._label_status = dict()

        prompt_label = ful.make_label(_LABEL_START_STR, alignment=(0.5, 0.5))

        self._top_level_test_list = gtk.VBox()
        self._top_level_test_list.pack_start(prompt_label, False, False)

        for name in _SUBTEST_LIST:
            label_box = self.make_subtest_label_box(name)
            self._top_level_test_list.pack_start(label_box, False, False)

        self._test_widget = gtk.EventBox()
        self._test_widget.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        self._test_widget.add(self._top_level_test_list)

        self._subtest_widget = None

        self.goto_next_subtest()

        ful.run_test_widget(self.job, self._test_widget,
            window_registration_callback=self.register_callbacks)

        failed_set = set(name for name, status in self._status_map.items()
                         if status is not ful.PASSED)
        if failed_set:
            raise error.TestFail('some subtest failed (%s)' %
                                 ', '.join(failed_set))

        factory.log('%s run_once finished' % self.__class__)
