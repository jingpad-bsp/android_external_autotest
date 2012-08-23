# -*- coding: utf-8 -*-
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import sys
import time
import yaml

import gobject
import gtk

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory_setup_modules
from cros.factory import event_log
from cros.factory.test import factory
from cros.factory.test import gooftools
from cros.factory.test import shopfloor
from cros.factory.test import task
from cros.factory.test import ui


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
                   " press SPACE to continue.\n"
                   "系統尚未就緒。\n"
                   "請修正紅色項目後按空白鍵重新檢查。")
    MSG_FORCE = ("Press 'f' to force starting finalization procedure.\n"
                 "按下 'f' 鍵以強迫開始最終程序。")
    MSG_READY = ("System is READY. Press SPACE to start FINALIZATION!\n"
                 "系統已準備就緒。 請按空白鍵開始最終程序!")
    MSG_POLLING = ("System is NOT ready. Please fix RED tasks.\n"
                   "系統尚未就緒。請修正紅色項目。")
    MSG_POLLING_READY = ("System is READY. Staring FINALIZATION!\n"
                         "系統已準備就緒。 開始最終程序!")

    def __init__(self, test_list, write_protection, polling_seconds,
                 allow_force_finalize):
        def create_label(message):
            return ui.make_label(message, fg=self.COLOR_DISABLED,
                                 alignment=(0, 0.5))
        self.updating = False
        self.write_protection = write_protection
        self.polling_seconds = polling_seconds
        self.polling_mode = (self.polling_seconds is not None)
        self.test_list = test_list
        self.allow_force_finalize = allow_force_finalize
        self.items = [(self.check_required_tests,
                       create_label("Verify no tests failed\n"
                                    "確認無測試項目失敗")),
                      (self.check_developer_switch,
                       create_label("Turn off Developer Switch\n"
                                    "停用開發者開關(DevSwitch)"))]
        if not write_protection:
            return

        # Items only enforced in write_protection mode.
        self.items += [
                       (self.check_write_protect,
                        create_label("Enable write protection pin\n"
                                     "確認硬體寫入保護已開啟"))]

    def check_developer_switch(self):
        """ Checks if developer switch button is disabled """
        try:
            gooftools.run('gooftool verify_switch_dev')
        except:
            return False
        return True

    def check_write_protect(self):
        """ Checks if hardware write protection pin is enabled """
        try:
            gooftools.run('gooftool verify_switch_wp')
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
            msg_pending = self.MSG_PENDING
            if self.allow_force_finalize:
                msg_pending += "\n\n" + self.MSG_FORCE
            msg_ready = self.MSG_READY
            if self.polling_mode:
                msg_pending = self.MSG_POLLING
                msg_ready = self.MSG_POLLING_READY
            self.label_status.set_label(msg_ready if all(self.results) else
                                        msg_pending)

        def next_test():
            if not items:
                update_summary()
                self.polling_scheduler()
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

    def polling_timeout(self):
        self.update_results()
        # Stop timeout callbacks.
        return False

    def polling_scheduler(self):
        if not self.polling_mode:
            return

        if all(self.results):
            self.stop()
        else:
            # schedule next polling event.
            gobject.timeout_add(self.polling_seconds * 1000,
                                self.polling_timeout)

    def window_key_press(self, widget, event):
        if self.updating:
            return True

        if event.keyval == ord('f') and self.allow_force_finalize:
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
        if not self.polling_mode:
            self.connect_window('key-press-event', self.window_key_press)


class FinalizeTask(task.FactoryTask):

    def __init__(self, write_protection, secure_wipe, upload_method,
                 test_states_path):
        self.write_protection = write_protection
        self.secure_wipe = secure_wipe
        self.upload_method = upload_method
        self.test_states_path = test_states_path

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

        command = 'gooftool -v 4 -l %s finalize' % factory.CONSOLE_LOG_PATH
        if not self.write_protection:
            self.alert('WRITE PROTECTION IS DISABLED.')
            command += ' --no_write_protect'
        if not self.secure_wipe:
            command += ' --fast'
        command += ' --upload_method "%s"' % upload_method
        command += ' --add_file "%s"' % self.test_states_path

        gooftools.run(command)

        # TODO(hungte) Use Reboot in test list to replace this, or add a
        # key-press check in developer mode.
        os.system("sync; sync; sync; shutdown -r now")
        self.stop()


class factory_Finalize(test.test):

    version = 3

    def run_once(self,
                 developer_mode=None,  # Deprecated parameter.
                 write_protection=True,
                 polling_seconds=None,
                 secure_wipe=False,
                 upload_method='none',
                 test_list_path=None,
                 allow_force_finalize=True):
        factory.log('%s run_once' % self.__class__)

        if developer_mode is not None:
            write_protection = not developer_mode
            factory.log('Warning: "developer_mode" param is deprecated.')

        test_list = factory.read_test_list(test_list_path)
        test_states = test_list.as_dict(
            factory.get_state_instance().get_test_states())

        test_states_path = os.path.join(factory.get_log_root(),
                                        'test_states')
        with open(test_states_path, 'w') as f:
            yaml.dump(test_states, f)

        self.tasks = [
                PreflightTask(test_list, write_protection, polling_seconds,
                              allow_force_finalize),
                FinalizeTask(write_protection, secure_wipe, upload_method,
                             test_states_path)]

        event_log.EventLog.ForAutoTest().Log('test_states',
                                             test_states=test_states)

        task.run_factory_tasks(self.job, self.tasks)

        factory.log('%s run_once finished' % repr(self.__class__))
