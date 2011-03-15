# -*- coding: utf-8 -*-
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import gtk
from gtk import gdk
import os
import time

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import gpio


# TODO(hungte) We may consider using real factory_Verify in the future.
class MiniVerifier(object):
    """ Simplified version of factory_Verify. """

    def __init__(self):
        self._gpio = gpio.Gpio(error.TestError)
        self._gpio.setup()

    def set_test_info(self, status_file, test_list):
        """ Configures the test list map """
        self.status_file = status_file
        self.test_list = test_list

    def read_gpio_uint(self, filename):
        """ Reads an unsigned integer from given GPIO entry
            Returns: >=0 for valid data, otherwise failure.
        """
        try:
            status = self._gpio.read(filename)
        except:
            return -1
        return status

    def check_developer_switch(self):
        """ Checks if developer switch button is disabled """
        return self.read_gpio_uint("developer_switch") == 0

    def check_write_protect(self):
        """ Checks if hardware write protection pin is enabled """
        return self.read_gpio_uint("write_protect") == 1

    def check_vboot_state(self):
        data = utils.system_output("dev_debug_vboot | grep ' OK$'",
                                   ignore_status=True)
        # factory.log(data)
        if (data.find('Verify firmware B') < 0 or
            data.find('Test kernel_subkey_b') < 0 or
            data.find('Test hd_kern_b.') < 0 or
            data.find('Verify hd_kern_b.blob with kernel_subkey_b') < 0):
            return False
        return True

    def check_required_tests(self):
        """ Checks if all previous tests are passed """
        # NOTE the real 'required test' check in factory_Verify also checks
        # "Google Required Tests", which is not verified here.
        db = factory.TestDatabase(self.test_list)
        status_map = factory.StatusMap(self.test_list, self.status_file, db)
        if status_map.filter_by_status(ful.FAILED):
            return False
        return True


class factory_PreFinalCheck(test.test):
    version = 2

    # messages for localization
    MSG_START = ("Press SPACE to start checking for finalization.\n"
                 "請按空白鍵開始檢查系統是否已可開始最終程序。")
    MSG_CHECKING = ("Checking system status for finalization...\n"
                    "正在檢查系統是否已可執行最終程序...")
    MSG_PENDING = ("System is NOT ready. Please fix RED tasks and then\n"
                   " press SPACE to continue,\n"
                   " or press 'f' to force starting finalization procedure.\n"
                   "系統尚未就緒。請修正紅色項目後按空白鍵以重新檢查，\n"
                   "或是按下 'f' 鍵以強迫開始最終程序。")
    MSG_READY = ("System is READY. Press SPACE to start FINALIZATION!\n"
                 "系統已準備就緒。 請按空白鍵開始最終程序!")

    # list of tasks to be checked in format ('name': 'label')
    CHECK_TASKS = {
        'required_tests': ("Verify all required tests are passed\n"
                           "確認所有必要測試已通過"),
        'developer_switch': ("Turn off Developer Switch\n"
                             "停用開發者開關 (Developer Switch)"),
        'write_protect': ("Enable write protection pin\n"
                          "確認硬體寫入保護已開啟"),
        'vboot_state': ("Keys for verified boot are matched\n"
                        "驗證開機所需各金鑰符合磁碟映像內容"),
    }

    def run_verify(self, vector):
        return getattr(self.verifier, 'check_' + vector)()

    def all_passed(self):
        assert(self.check_results)
        return all(self.check_results)

    def set_task_as_disabled(self, label_widget):
        label_widget.modify_fg(gtk.STATE_NORMAL, self.COLOR_DISABLED)

    def set_task_by_result(self, label_widget, result):
        if result:
            label_widget.modify_fg(gtk.STATE_NORMAL, self.COLOR_PASSED)
        else:
            label_widget.modify_fg(gtk.STATE_NORMAL, self.COLOR_ACTIVE)

    def update_status(self):
        self.label_status.set_label(self.MSG_CHECKING)
        for label in self.check_labels:
            self.set_task_as_disabled(label)

        # Warning: to provide some visual feedback for operator, here we try to
        # process GTK events for redrawing window, and sleep for one second.
        # This also implies we must make sure there's no reentrant.
        gtk.main_iteration(False)
        time.sleep(1)

        self.check_results = [self.run_verify(vector)
                              for vector in self.CHECK_TASKS]
        for label, result in zip(self.check_labels, self.check_results):
            self.set_task_by_result(label, result)

        # update the summary
        if self.all_passed():
            self.label_status.set_label(self.MSG_READY)
        else:
            self.label_status.set_label(self.MSG_PENDING)

    def key_release_callback(self, widget, event):
        if event.keyval == ord('f'):
            factory.log("WARNING: Operator manually forced finalization.")
            gtk.main_quit()
        elif event.keyval == ord(' '):
            if self.all_passed():
                gtk.main_quit()
            else:
                if self.last_check and (time.time() < self.last_check + 1):
                    # ignore flooding events in 1 second
                    return True
                widget.handler_block(self.key_released_handler_id)
                self.update_status()
                widget.handler_unblock(self.key_released_handler_id)
                self.last_check = time.time()
        return True

    def register_callback(self, window):
        self.key_released_handler_id = window.connect(
                'key-release-event', self.key_release_callback)
        window.add_events(gdk.KEY_RELEASE_MASK)

    def create_disabled_label(self, message):
        return ful.make_label(
                message, fg=self.COLOR_DISABLED, alignment=(0, 0.5))

    def run_once(self, status_file_path=None, test_list=None):
        # configure verifier
        self.verifier = MiniVerifier()
        self.verifier.set_test_info(status_file_path, test_list)
        self.last_check = None

        self.COLOR_DISABLED = gtk.gdk.Color(0x7000, 0x7000, 0x7000)
        self.COLOR_PASSED = ful.LIGHT_GREEN
        self.COLOR_ACTIVE = ful.RED

        # build check list from self.CHECK_TASKS
        self.check_results = []
        self.check_labels = []
        for message in self.CHECK_TASKS.values():
            self.check_labels.append(self.create_disabled_label(message))
            self.check_results.append(False)

        # build main window
        self.label_status = ful.make_label(self.MSG_START, fg=ful.WHITE)
        vbox = gtk.VBox()
        vbox.set_spacing(20)
        vbox.pack_start(self.label_status, False, False)
        for label in self.check_labels:
            vbox.pack_start(label, False, False)
        widget = gtk.EventBox()
        widget.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        widget.add(vbox)

        ful.run_test_widget(self.job, widget,
                            window_registration_callback=self.register_callback)
