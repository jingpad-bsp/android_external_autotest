# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import os
import re
import time

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import gooftools
from autotest_lib.client.cros.factory import shopfloor
from autotest_lib.client.cros.factory import ui as ful


class factory_Finalize(test.test):
    version = 1

    def alert(self, message, times=3):
        """Alerts user for given message."""
        for i in range(times, 0, -1):
            factory.log(('WARNING: Factory Finalize: %s. ' +
                         'THIS DEVICE CANNOT BE QUALIFIED. ' +
                         '(continue in %d seconds)') % (message, i))
            time.sleep(1)

    def check_google_required_tests(self, status_file, test_list_path):
        """ Checks if all previous and Google Required Tests are passed. """
        # check if all previous tests are passed.
        test_list = factory.read_test_list(test_list_path)
        state_map = test_list.get_state_map()
        failed_list = [test for test in test_list.walk()
                       if state_map[test].status == factory.TestState.FAILED]
        if failed_list:
            failed = ','.join([x.path for x in failed_list])
            raise error.TestFail('Some previous tests failed: %s' % failed)
        factory.log('All previous tests are PASSED.')

    def normalize_upload_method(self, original_method):
        """ Build the report file name and solve variables. """

        method = original_method
        if method in [None, 'none']:
            # gooftool accepts only 'none', not empty string.
            return 'none'

        if method == 'shopfloor':
            method = 'shopfloor:%s#%s' % (shopfloor.get_server_url(),
                                          shopfloor.get_serial_number())

        factory.log('norm_upload_method: %s -> %s' % (original_method, method))
        return method

    def run_once(self,
                 developer_mode=False,
                 secure_wipe=False,
                 upload_method='none',
                 subtest_tag=None,
                 status_file_path=None,
                 test_list_path=None):

        if developer_mode:
            self.alert('DEVELOPER MODE ENABLED')
        else:
            # verify previous test results
            self.check_google_required_tests(status_file_path, test_list_path)

        # solve upload file names
        upload_method = self.normalize_upload_method(upload_method)

        # get report information
        hwid_cfg = factory.get_shared_data('hwid_cfg')

        args = ['gooftool',
                '--developer_finalize' if developer_mode else '--finalize',
                '--verbose',
                '--wipe_method "%s"' % ('secure' if secure_wipe else 'fast'),
                '--report_tag "%s"' % hwid_cfg,
                '--upload_method "%s"' % upload_method,
                ]

        cmd = ' '.join(args)
        gooftools.run(cmd)

        # TODO(hungte) use Reboot in test list to replace this?
        os.system("sync; sync; sync; shutdown -r now")
