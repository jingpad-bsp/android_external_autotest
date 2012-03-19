# -*- coding: utf-8 -*-
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import sys
import thread
import time

import gobject
import gtk

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import gooftools
from autotest_lib.client.cros.factory import shopfloor
from autotest_lib.client.cros.factory import ui


class PreflightChecker(object):
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
        # Change system to "checking" state.
        for _, label in self.items:
            label.modify_fg(gtk.STATE_NORMAL, self.COLOR_DISABLED)
            gtk.main_iteration(False)
        self.label_status.set_label(self.MSG_CHECKING)
        gtk.main_iteration(False)

        # In developer mode, provide more visual feedback.
        if self.developer_mode:
            gtk.main_iteration(False)
            time.sleep(.5)

        self.results = []
        result_message = self.MSG_READY

        for checker, label in self.items:
            result = checker()
            if not result:
                result_message = self.MSG_PENDING
            label.modify_fg(gtk.STATE_NORMAL,
                            self.COLOR_PASSED if result else self.COLOR_FAILED)
            self.results.append(result)
            gtk.main_iteration(False)
        self.label_status.set_label(result_message)

    def key_press_callback(self, widget, event):
        stop_preflight = False
        if event.keyval == ord('f'):
            factory.log("WARNING: Operator manually forced finalization.")
            stop_preflight= True
        elif event.keyval == ord(' '):
            if all(self.results):
                stop_preflight = True
            else:
                self.update_results()
        else:
            return False
        if stop_preflight:
            self.stop()
        return True

    def start(self, window, container, on_stop):
        self.on_stop = on_stop
        self.container = container
        self.results = [False]

        # Build main window.
        self.label_status = ui.make_label('', fg=ui.WHITE)
        vbox = gtk.VBox()
        vbox.set_spacing(20)
        vbox.pack_start(self.label_status, False, False)
        for _, label in self.items:
            vbox.pack_start(label, False, False)
        widget = gtk.EventBox()
        self.widget = vbox
        container.add(self.widget)
        container.show_all()
        window.add_events(gtk.gdk.KEY_PRESS_MASK)
        self.callback = (window, window.connect('key-press-event',
                                                self.key_press_callback))
        gtk.main_iteration(True)
        self.update_results()

    def stop(self):
        (window, callback_id) = self.callback
        self.container.remove(self.widget)
        self.on_stop(self)


class factory_Finalize(test.test):
    version = 2

    MESSAGE_FINALIZING = 'Finalizing, please wait...'

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

    def stop_task(self, task):
        factory.log("Stopping task: %s" % task.__class__.__name__)
        self.tasks.remove(task)
        self.find_next_task()

    def find_next_task(self):
        if self.tasks:
            task = self.tasks[0]
            factory.log("Starting task: %s" % task.__class__.__name__)
            task.start(self.window, self.container, self.stop_task)
        else:
            # No more tasks - try to do finalize.
            self.label = ui.make_label(self.MESSAGE_FINALIZING)
            self.container.add(self.label)
            self.container.show_all()

            thread.start_new_thread(self.worker_thread, ())

    def run_once(self,
                 developer_mode=False,
                 secure_wipe=False,
                 upload_method='none',
                 test_list_path=None):

        factory.log('%s run_once' % self.__class__)
        gtk.gdk.threads_init()

        self.developer_mode = developer_mode
        self.secure_wipe = secure_wipe
        self.upload_method = upload_method
        test_list = factory.read_test_list(test_list_path)

        def register_window(window):
            self.window = window
            self.find_next_task()
            return True

        self.container = gtk.VBox()
        self.tasks = [PreflightChecker(test_list, developer_mode)]
        ui.run_test_widget(self.job, self.container,
                            window_registration_callback=register_window)

        factory.log('%s run_once finished' % repr(self.__class__))

    def worker_thread(self):
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

        # TODO(hungte) use Reboot in test list to replace this?
        os.system("sync; sync; sync; shutdown -r now")
        gobject.idle_add(gtk.main_quit)
