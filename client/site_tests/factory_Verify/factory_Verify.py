# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import time

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


GPIO_ROOT = '/home/gpio'
GOOGLE_REQUIRED_TESTS = [ 'GRT_HWComponents', 'GRT_DevRec' ]


def init_gpio(gpio_root=GPIO_ROOT):
    """ initializes GPIO in GPIO_ROOT """
    if os.path.exists(gpio_root):
        utils.system("rm -rf '%s'" % gpio_root)
    utils.system("mkdir '%s'" % (gpio_root))
    utils.system("/usr/sbin/gpio_setup")


class factory_Verify(test.test):
    version = 1

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

        init_gpio()
        status = open(os.path.join(GPIO_ROOT, "developer_switch")).read()
        status_val = int(status)
        if status_val != 0:
            raise error.TestFail('Developer Switch Button is enabled')

    def check_flashrom_write_protect(self, do_check):
        """ Enables and checks write protection for flashrom """
        if not do_check:
            self.alert_bypassed("FLASHROM WRITE PROTECTION")
            return

        factory.log('enable write protect (factory_EnableWriteProtect)')
        self.job.run_test('factory_EnableWriteProtect')

        # verify if write protection range is properly fixed,
        # and all bits in RW is writable.
        factory.log('verify write protect (hardware_EepromWriteProtect)')
        if not self.job.run_test('hardware_EepromWriteProtect'):
            raise error.TestFail('Flashrom write protection test failed.')

    def check_google_required_tests(self, do_check, status_file, test_list):
        """ Checks if all previous and Google Required Tests are passed. """
        if not do_check:
            self.alert_bypassed('REQUIRED TESTS')
            return

        # check if all previous tests are passed.
        db = factory.TestDatabase(test_list)
        status_map = factory.StatusMap(test_list, status_file, db)
        failed_list = status_map.filter(ful.FAILED)
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
                 status_file_path=None,
                 test_list=None):

        # apply each final tests
        self.check_google_required_tests(check_required_tests,
                                         status_file_path,
                                         test_list)
        self.check_developer_switch(check_developer_switch)
        self.check_flashrom_write_protect(check_and_enable_write_protect)
