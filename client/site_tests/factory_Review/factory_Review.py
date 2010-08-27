# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This is an example factory test that does not really do anything --
# it displays a message in the center of the testing area, as
# communicated by arguments to run_once().  This test makes use of the
# factory_ui_lib library to display its UI, and to monitor keyboard
# events for test-switching triggers.  This test can be terminated by
# typing SHIFT-Q.


import gtk
import pango
import sys

from gtk import gdk

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


class factory_Review(test.test):
    version = 1

    def run_once(self,
                 status_file_path=None,
                 test_list=None):

        factory.log('%s run_once' % self.__class__)

        status_map = factory.StatusMap(test_list, status_file_path)
        untested = status_map.filter(ful.UNTESTED)
        passed = status_map.filter(ful.PASSED)
        failed = status_map.filter(ful.FAILED)

        top_label = ful.make_label('UNTESTED=%d\t' % len(untested) +
                               'PASSED=%d\t' % len(passed) +
                               'FAILED=%d' % len(failed))

        # decompose automated sequence tests
        failure_report_list =[]
        for t in failed:
            t_name = t.label_en
            if not isinstance(t, factory.AutomatedSequence):
                # Simple Test
                err_msg = status_map.lookup_error_msg(t)
                failure_report_list.append('%s: %s' % (t_name, err_msg))
                continue
            # Complex Test
            for subtest in t.subtest_list:
                if status_map.lookup_status(subtest) != ful.FAILED:
                    continue
                err_msg = status_map.lookup_error_msg(subtest)
                failure_report_list.append(
                        '%s: (%s) %s' % (t_name, subtest.label_en, err_msg))
        failure_report = ful.make_label('\n'.join(failure_report_list))

        vbox = gtk.VBox()
        vbox.set_spacing(20)
        vbox.pack_start(top_label, False, False)
        vbox.pack_start(failure_report, False, False)

        test_widget = gtk.EventBox()
        test_widget.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        test_widget.add(vbox)

        ful.run_test_widget(self.job, test_widget)

        factory.log('%s run_once finished' % self.__class__)
