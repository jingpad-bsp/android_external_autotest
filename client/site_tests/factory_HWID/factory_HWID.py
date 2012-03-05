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

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import shopfloor
from autotest_lib.client.cros.factory import ui as ful


class factory_HWID(test.test):
    version = 1

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

    def shop_floor_thread(self):
        """Task thread for writing HWID by shop floor system."""
        def update_label(text):
            with ful.gtk_lock:
                self.label.set_text(text)
        try:
            update_label("Fetching HWID information...")
            hwid = shopfloor.get_hwid()

            update_label("Writing HWID: [%s]" % hwid)
            self.write_hwid(hwid)
        except:
            self._fail_msg = "Failed writing HWID: %s" % sys.exc_info()[1]
            logging.exception("Execption when writing HWID by shop floor")
        finally:
            gobject.idle_add(gtk.main_quit)

    def run_shop_floor(self):
        """Runs with shop floor system."""
        self.label = ful.make_label('Preparing HWID...')
        test_widget = self.label
        thread.start_new_thread(self.shop_floor_thread, ())
        ful.run_test_widget(self.job, test_widget)

    def run_interactively(self):
        """Runs interactively (without shop floor system)."""
        # TODO(hungte) A complete user interface to select modules
        self._fail_msg = "Interactive mode HWID probing is not implemented yet."

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
