# -*- coding: utf-8 -*-
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import sys
import time

import gtk

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import gooftools
from autotest_lib.client.cros.factory import shopfloor
from autotest_lib.client.cros.factory import task
from autotest_lib.client.cros.factory import ui


_MSG_FINALIZING = 'Finalizing, please wait...'


class PreflightTask(task.FactoryTask):
    """Checks if the system is ready for finalization."""

    # User interface theme
    COLOR_DISABLED = gtk.gdk.Color(0x7000, 0x7000, 0x7000)
    COLOR_PASSED = ui.LIGHT_GREEN
    COLOR_FAILED = ui.RED

    # Messages for localization
    MSG_CHECKING = ("Checking system status for finalization...\n"
                    "正在檢查系統是否已可執行最終程序...")
    MSG_PENDING = ("System is NOT ready. Please fix RED tasks and then\n"
                   " press SPACE to continue,\n"
                   " or press 'f' to force starting finalization procedure.\n"
                   "系統尚未就緒。\n"
                   "請修正紅色項目後按空白鍵重新檢查，\n"
                   "或是按下 'f' 鍵以強迫開始最終程序。")
    MSG_READY = ("System is READY. Press SPACE to start FINALIZATION!\n"
                 "系統已準備就緒。 請按空白鍵開始最終程序!")

    def __init__(self, test_list, developer_mode):
        def create_label(message):
            return ui.make_label(message, fg=self.COLOR_DISABLED,
                                 alignment=(0, 0.5))
        self.updating = False
        self.developer_mode = developer_mode
        self.test_list = test_list
        self.items = [(self.check_required_tests,
                       create_label("Verify no tests failed\n"
                                    "確認無測試項目失敗"))]
        if developer_mode:
            return

        # Items only enforced in non-developer mode.
        self.items += [(self.check_developer_switch,
                        create_label("Turn off Developer Switch\n"
                                     "停用開發者開關(DevSwitch)")),
                       (self.check_write_protect,
                        create_label("Enable write protection pin\n"
                                     "確認硬體寫入保護已開啟"))]

    def check_developer_switch(self):
        """ Checks if developer switch button is disabled """
        try:
            gooftools.run('gooftool --verify_switch_dev --verbose')
        except:
            return False
        return True

    def check_write_protect(self):
        """ Checks if hardware write protection pin is enabled """
        try:
            gooftools.run('gooftool --verify_switch_wp --verbose')
        except:
            return False
        return True

    def check_required_tests(self):
        """ Checks if all previous tests are passed """
        state_map = self.test_list.get_state_map()
        return not any(x.status == factory.TestState.FAILED
                       for x in state_map.values())

    def update_results(self):
        self.updating = True
        for _, label in self.items:
            label.modify_fg(gtk.STATE_NORMAL, self.COLOR_DISABLED)
        self.label_status.set_label(self.MSG_CHECKING)

        def update_summary():
            self.updating = False
            self.label_status.set_label(
                    self.MSG_READY if all(self.results) else self.MSG_PENDING)
            # In developer mode, provide more visual feedback.
            if self.developer_mode:
                time.sleep(.5)

        def next_test():
            if not items:
                update_summary()
                return
            checker, label = items.pop(0)
            result = checker()
            label.modify_fg(gtk.STATE_NORMAL,
                            self.COLOR_PASSED if result else self.COLOR_FAILED)
            self.results.append(result)
            task.schedule(next_test)

        # Perform all tests
        items = self.items[:]
        self.results = []
        task.schedule(next_test)

    def window_key_press(self, widget, event):
        if self.updating:
            return True

        if event.keyval == ord('f'):
            factory.log("WARNING: Operator manually forced finalization.")
        elif event.keyval == ord(' '):
            if not all(self.results):
                self.update_results()
                return True
        else:
            return False

        self.stop()
        return True

    def start(self):
        self.results = [False]

        # Build main window.
        self.label_status = ui.make_label('', fg=ui.WHITE)
        vbox = gtk.VBox()
        vbox.set_spacing(20)
        vbox.pack_start(self.label_status, False, False)
        for _, label in self.items:
            vbox.pack_start(label, False, False)
        self.widget = vbox
        self.add_widget(self.widget)
        task.schedule(self.update_results)
        self.connect_window('key-press-event', self.window_key_press)


class FinalizeTask(task.FactoryTask):

    def __init__(self, developer_mode, secure_wipe, upload_method):
        self.developer_mode = developer_mode
        self.secure_wipe = secure_wipe
        self.upload_method = upload_method

    def alert(self, message, times=3):
        """Alerts user that a required test is bypassed."""
        for i in range(times, 0, -1):
            factory.log(('WARNING: Factory Finalize: %s. ' +
                         'THIS DEVICE CANNOT BE QUALIFIED. ' +
                         '(continue in %d seconds)') % (message, i))
            time.sleep(1)

    def normalize_upload_method(self, original_method):
        """Build the report file name and solve variables."""
        method = original_method
        if method in [None, 'none']:
            # gooftool accepts only 'none', not empty string.
            return 'none'

        if method == 'shopfloor':
            method = 'shopfloor:%s#%s' % (shopfloor.get_server_url(),
                                          shopfloor.get_serial_number())

        factory.log('norm_upload_method: %s -> %s' % (original_method, method))
        return method

    def start(self):
        self.add_widget(ui.make_label(_MSG_FINALIZING))
        task.schedule(self.do_finalize)

    def do_finalize(self):
        upload_method = self.normalize_upload_method(self.upload_method)
        hwid_cfg = factory.get_shared_data('hwid_cfg')

        command = '--finalize'
        if self.developer_mode:
            self.alert('DEVELOPER MODE ENABLED')
            command = '--developer_finalize'

        args = ['gooftool',
                command,
                '--verbose',
                '--wipe_method "%s"' % ('secure' if self.secure_wipe else
                                        'fast'),
                '--report_tag "%s"' % hwid_cfg,
                '--upload_method "%s"' % upload_method,
                ]

        cmd = ' '.join(args)
        gooftools.run(cmd)

        # TODO(hungte) Use Reboot in test list to replace this, or add a
        # key-press check in developer mode.
        os.system("sync; sync; sync; shutdown -r now")
        self.stop()


class factory_Finalize(test.test):

    version = 3

    def run_once(self,
                 developer_mode=False,
                 secure_wipe=False,
                 upload_method='none',
                 test_list_path=None):

        factory.log('%s run_once' % self.__class__)

        test_list = factory.read_test_list(test_list_path)
        self.tasks = [PreflightTask(test_list, developer_mode),
                      FinalizeTask(developer_mode, secure_wipe, upload_method)]

        task.run_factory_tasks(self.job, self.tasks)

        factory.log('%s run_once finished' % repr(self.__class__))
