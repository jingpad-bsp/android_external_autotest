# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import os
import re
import time

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import gooftools


class factory_Finalize(test.test):
    version = 1

    def alert_bypassed(self, target, times=3):
        """ Alerts user that a required test is bypassed. """
        for i in range(times, 0, -1):
            factory.log(('WARNING: Factory Finalize: <%s> IS BYPASSED. ' +
                         'THIS DEVICE CANNOT BE QUALIFIED. ' +
                         '(continue in %d seconds)') % (target, i))
            time.sleep(1)

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
        factory.log('All previous tests are PASSED.')

    def collect_vpd_values(self):
        ''' Collects VPD properties and return as dictionary '''
        vpd_dict = {}
        vpd_data = utils.system_output(
                "(vpd -l -i RO_VPD; vpd -l -i RW_VPD) | grep '\"=\"'",
                ignore_status=True).strip()
        # the output of vpd is "A"="B"

        for line in vpd_data.splitlines():
            matched = re.match('"(.*)"="(.*)"$', line)
            if not matched:
                continue
            vpd_dict['vpd_' + matched.group(1)] = matched.group(2)
        return vpd_dict

    def normalize_upload_method(self, original_method):
        """ Build the report file name and solve variables. """

        method = original_method
        if method.startswith('none'):
            return method

        if method.startswith('ftp') and method.endswith('/'):
            # Need a unique file name. Simulte old method to create a hash.
            method = method + '%(hash).log%(gz)'

        filename_params = {
                'gz': '.gz',
                'hash': hashlib.sha1(
                        open(factory.LOG_PATH, 'rb').read()).hexdigest(),
        }
        if method.find('%(vpd_') >= 0:
            factory.log('Upload target has VPD variables. Collecting VPD...')
            filename_params.update(self.collect_vpd_values())

        # To match python syntax, postfix every variable with 's'.
        method = re.sub('(%\([^)]*\))', r'\1s', method)
        method = method % filename_params

        factory.log('norm_upload_method: %s -> %s' % (original_method, method))
        return method

    def run_once(self,
                 check_required_tests=True,
                 check_and_enable_write_protect=True,
                 secure_wipe=False,
                 upload_method='none',
                 subtest_tag=None,
                 status_file_path=None,
                 test_list=None):

        # verify previous test results
        self.check_google_required_tests(check_required_tests,
                                         status_file_path,
                                         test_list)
        # solve upload file names
        upload_method = self.normalize_upload_method(upload_method)

        # get report information
        hwid_cfg = factory.get_shared_data('hwid_cfg')

        args = ['gooftool',
                '--finalize',
                '--verbose',
                '--wipe_method "%s"' % ('secure' if secure_wipe else 'fast'),
                '--report_tag "%s"' % hwid_cfg,
                '--upload_method "%s"' % upload_method,
                ]
        if not check_and_enable_write_protect:
            self.alert_bypassed('WRITE PROTECTION')
            args.append('--debug_dryrun_wpfw')

        cmd = ' '.join(args)
        gooftools.run(cmd)

        # TODO(hungte) use Reboot in test list to replace this?
        os.system("sync; sync; sync; shutdown -r now")
