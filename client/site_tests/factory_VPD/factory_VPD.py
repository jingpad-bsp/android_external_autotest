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


class factory_VPD(test.test):
    version = 1

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

    def shop_floor_thread(self):
        """Task thread for writing VPD by shop floor system."""
        def update_label(text):
            with gtk.gdk.lock:
                self.label.set_text(text)
        try:
            update_label("Fetching VPD information...")
            vpd = shopfloor.get_vpd()

            # Flatten key-values in VPD dictionary.
            vpd_list = []
            for vpd_type in ('ro', 'rw'):
                vpd_list += ['%s: %s = %s' % (vpd_type, key, vpd[vpd_type][key])
                             for key in sorted(vpd[vpd_type])]

            update_label("Writing VPD:\n%s" % '\n'.join(vpd_list))
            self.write_vpd(vpd)
        except:
            self._fail_msg = "Failed writing VPD: %s" % sys.exc_info()[1]
            logging.exception("Exception when writing VPD by shop floor")
        finally:
            gobject.idle_add(gtk.main_quit)

    def run_shop_floor(self):
        """Runs with shop floor system."""
        self.label = ful.make_label('Preparing VPD...')
        test_widget = self.label
        thread.start_new_thread(self.shop_floor_thread, ())
        ful.run_test_widget(self.job, test_widget)

    def run_interactively(self):
        """Runs interactively (without shop floor system)."""
        # TODO(hungte) A complete user interface to select VPD values.
        self._fail_msg = "Interactive mode VPD writing is not implemented yet."

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
