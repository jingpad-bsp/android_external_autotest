# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import time

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import site_gpio


GOOGLE_REQUIRED_TESTS = [ 'GRT_HWComponents', 'GRT_DevRec' ]


class factory_Verify(test.test):
    version = 3

    def alert_bypassed(self, target, times=3):
        """ Alerts user that a required test is bypassed. """
        for i in range(times, 0, -1):
            factory.log(('WARNING: Factory Final Verify: <%s> IS BYPASSED. ' +
                         'THIS DEVICE CANNOT BE QUALIFIED. ' +
                         '(continue in %d seconds)') % (target, i))
            time.sleep(1)

    def check_developer_switch(self, do_check):
        """ Checks if developer switch button is in disabled state """
        if not do_check:
            self.alert_bypassed("DEVELOPER SWITCH BUTTON")
            return

        gpio = site_gpio.Gpio(error.TestFail)
        gpio.setup()
        property_name = 'developer_switch'
        try:
            status_val = gpio.read(property_name)
        except:
            raise error.TestFail('Cannot read GPIO value: %s' % property_name)

        if status_val != 0:
            raise error.TestFail('Developer Switch Button is enabled')

    def check_flashrom_write_protect(self, do_check, subtest_tag):
        """ Enables and checks write protection for flashrom """
        if not do_check:
            self.alert_bypassed("FLASHROM WRITE PROTECTION")
            return

        # this is an important message, so print it several times to alert user
        for i in range(3):
            factory.log('ENABLE WRITE PROTECTION (factory_EnableWriteProtect)')
        if not self.job.run_test('factory_EnableWriteProtect', tag=subtest_tag):
            raise error.TestFail('Flashrom write protection test failed.')

    def check_google_required_tests(self, do_check, status_file, test_list):
        """ Checks if all previous and Google Required Tests are passed. """
        if not do_check:
            self.alert_bypassed('REQUIRED TESTS')
            return

        # check if all previous tests are passed.
        db = factory.TestDatabase(test_list)
        status_map = factory.StatusMap(test_list, status_file, db)
        failed_list = status_map.filter_by_status(ful.FAILED)
        if failed_list:
            failed = ','.join([db.get_unique_id_str(t) for t in failed_list])
            raise error.TestFail('Some previous tests failed: %s' % failed)

        # check if all Google Required Tests are passed
        missing = []
        for g in GOOGLE_REQUIRED_TESTS:
            t = db.get_test_by_unique_name(g)
            if status_map.lookup_status(t) != ful.PASSED:
                missing.append('%s(%s)' % (g, db.get_unique_id_str(t)))
        if missing:
            missing_msg = ', '.join(missing)
            raise error.TestFail('You need to execute following ' +
                                 'Google Required Tests: %s' % missing_msg)

    def run_once(self,
                 check_required_tests=True,
                 check_developer_switch=True,
                 check_and_enable_write_protect=True,
                 subtest_tag=None,
                 status_file_path=None,
                 test_list=None):

        # apply each final tests
        self.check_google_required_tests(check_required_tests,
                                         status_file_path,
                                         test_list)
        self.check_developer_switch(check_developer_switch)
        self.check_flashrom_write_protect(check_and_enable_write_protect,
                                          subtest_tag)
