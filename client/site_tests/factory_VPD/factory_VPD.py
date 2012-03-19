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

import serial_task
import region_task

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import shopfloor
from autotest_lib.client.cros.factory import ui as ful


_MESSAGE_PREPARE_VPD = "Preparing VPD..."

class factory_VPD(test.test):
    version = 2

    def write_vpd(self, vpd):
        """Writes a VPD structure into system.

        @param vpd: A dictionary with 'ro' and 'rw' keys, each associated with a
          key-value VPD data set.
        """
        def shell(command):
            factory.log(command)
            utils.system(command)

        def format_vpd_parameter(vpd_dict):
            """Formats a key-value dictionary into VPD syntax."""
            # Writes in sorted ordering so the VPD structure will be more
            # deterministic.
            return ' '.join(('-s "%s"="%s"' % (key, vpd_dict[key])
                             for key in sorted(vpd_dict)))

        VPD_LIST = (('RO_VPD', 'ro'), ('RW_VPD', 'rw'))
        with tempfile.NamedTemporaryFile() as temp_file:
            name = temp_file.name
            for (section, vpd_type) in VPD_LIST:
                if not vpd.get(vpd_type, None):
                    continue
                parameter = format_vpd_parameter(vpd[vpd_type])
                shell('vpd -i %s %s' % (section, parameter))

    def worker_thread(self, vpd):
        """Task thread for writing VPD."""
        def update_label(text):
            with ful.gtk_lock:
                self.label.set_text(text)
        if vpd is None:
            update_label("Fetching VPD information...")
            vpd = shopfloor.get_vpd()

        # Flatten key-values in VPD dictionary.
        vpd_list = []
        for vpd_type in ('ro', 'rw'):
            vpd_list += ['%s: %s = %s' % (vpd_type, key, vpd[vpd_type][key])
                         for key in sorted(vpd[vpd_type])]

        update_label("Writing VPD:\n%s" % '\n'.join(vpd_list))
        self.write_vpd(vpd)

    def run_shop_floor(self):
        """Runs with shop floor system."""
        self.label = ful.make_label(_MESSAGE_PREPARE_VPD)
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
            # No more tasks - try to write into VPD.
            self.label = ful.make_label(_MESSAGE_PREPARE_VPD)
            self.container.add(self.label)
            self.container.show_all()
            thread.start_new_thread(self.worker_thread, (self.vpd, ))

    def run_interactively(self):
        """Runs interactively (without shop floor system)."""
        def register_window(window):
            self.window = window
            self.find_next_task()
            return True
        self.vpd = {'ro': {}, 'rw': {}}
        self.container = gtk.VBox()
        self.tasks = [serial_task.SerialNumberTask(self.vpd),
                      region_task.SelectRegionTask(self.vpd)]
        ful.run_test_widget(self.job, self.container,
                            window_registration_callback=register_window)


    def run_once(self):
        factory.log('%s run_once' % self.__class__)

        gtk.gdk.threads_init()
        if shopfloor.is_enabled():
            self.run_shop_floor()
        else:
            self.run_interactively()

        factory.log('%s run_once finished' % repr(self.__class__))
