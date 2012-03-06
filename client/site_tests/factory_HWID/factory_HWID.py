# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import sys
import tempfile
import thread

import gobject
import gtk
from gtk import gdk

import select_task

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import shopfloor
from autotest_lib.client.cros.factory import ui as ful


_MESSAGE_PREPARE = "Preparing HWID..."

class factory_HWID(test.test):
    version = 2

    def write_hwid(self, hwid):
        """Writes system HWID by assigned spec.

        @param hwid: A complete HWID, or BOM-VARIANT pair.
        """
        # TODO(hungte) Replace this by gooftool, plus partial matching.
        # When the input is not a complete HWID (i.e., BOM-VARIANT pair), select
        # and derive the complete ID from active HWIDs in current database.
        # Ex: input="BLUE A" => matched to "MARIO BLUE A-B 6868".
        def shell(command):
            factory.log(command)
            utils.system(command)
        with tempfile.NamedTemporaryFile() as temp_file:
            name = temp_file.name
            shell("flashrom -i GBB -r '%s'" % name)
            shell("gbb_utility -s --hwid='%s' '%s'" % (hwid, name))
            # TODO(hungte) If the HWID is already set correctly, no need to
            # write again.
            shell("flashrom -i GBB -w '%s' --fast-verify" % name)

    def worker_thread(self, data):
        """Task thread for writing HWID."""
        def update_label(text):
            with ful.gtk_lock:
                self.label.set_text(text)
        try:
            if data is None:
                update_label("Fetching HWID information...")
                hwid = shopfloor.get_hwid()
            else:
                assert 'hwid' in data, "Missing HWID after selection."
                hwid = data.get('hwid', None)

            if not hwid:
                raise ValueError("Invalid empty HWID")
            else:
                update_label("Writing HWID: [%s]" % hwid)
                self.write_hwid(hwid)
        except:
            self._fail_msg = "Failed writing HWID: %s" % sys.exc_info()[1]
            logging.exception("Exception when writing HWID")
        finally:
            gobject.idle_add(gtk.main_quit)

    def run_shop_floor(self):
        """Runs with shop floor system."""
        self.label = ful.make_label(_MESSAGE_PREPARE)
        thread.start_new_thread(self.worker_thread, (None, ))
        ful.run_test_widget(self.job, self.label)

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
            # No more tasks - try to write data.
            self.label = ful.make_label(_MESSAGE_PREPARE)
            self.container.add(self.label)
            self.container.show_all()
            thread.start_new_thread(self.worker_thread, (self.data, ))

    def run_interactively(self):
        """Runs interactively (without shop floor system)."""
        def register_window(window):
            self.window = window
            self.find_next_task()
            return True
        self.data = {'hwid': None}
        self.container = gtk.VBox()
        self.tasks = [select_task.SelectHwidTask(self.data)]
        ful.run_test_widget(self.job, self.container,
                            window_registration_callback=register_window)


    def run_once(self):
        factory.log('%s run_once' % self.__class__)
        self._fail_msg = None

        gtk.gdk.threads_init()
        if shopfloor.is_enabled():
            self.run_shop_floor()
        else:
            self.run_interactively()

        factory.log('%s run_once finished' % repr(self.__class__))
        if self._fail_msg:
            raise error.TestFail(self._fail_msg)
