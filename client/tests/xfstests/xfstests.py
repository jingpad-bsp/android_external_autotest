# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, re, glob, logging, shutil
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import test, utils

class xfstests(test.test):
    """
    Runs a single test of the xfstests suite.
    """

    XFS_TESTS_PATH='/usr/local/xfstests'
    version = 2

    PASSED_RE = re.compile(r'Passed all \d+ tests')
    FAILED_RE = re.compile(r'Failed \d+ of \d+ tests')
    TEST_RE = re.compile(r'(?P<name>\d+)\.out')
    NA_RE = re.compile(r'Passed all 0 tests')
    NA_DETAIL_RE = re.compile(r'(\d{3})\s*(\[not run\])\s*(.*)')


    def _get_available_tests(self, fs):
        os.chdir(os.path.join(self.XFS_TESTS_PATH, 'tests', fs))
        tests = glob.glob('*.out*')
        tests_list = []
        for t in tests:
            t_m = self.TEST_RE.match(t)
            if t_m:
                t_name = t_m.group('name')
                if t_name not in tests_list and os.path.exists(t_name):
                    tests_list.append(t_name)
        tests_list.sort()
        return tests_list


    def _run_sub_test(self, test):
        os.chdir(self.XFS_TESTS_PATH)
        logging.debug("Environment variables: %s", os.environ)
        output = utils.system_output(
                'bash ./check %s' % os.path.join('tests', test),
                ignore_status=True,
                retain_output=True)
        lines = output.split('\n')
        result_line = lines[-2]
        result_full = os.path.join('results', '.'.join([test, 'full']))
        result_full_loc = os.path.join(self.XFS_TESTS_PATH, result_full)
        if os.path.isfile(result_full_loc):
            shutil.copyfile(result_full_loc,
                            os.path.join(self.resultsdir, 'full'))

        if self.NA_RE.match(result_line):
            detail_line = lines[-3]
            match = self.NA_DETAIL_RE.match(detail_line)
            if match is not None:
                error_msg = match.groups()[2]
            else:
                error_msg = 'Test dependency failed, test not run'
            raise error.TestNAError(error_msg)

        elif self.FAILED_RE.match(result_line):
            raise error.TestError('Test error, check debug logs for complete '
                                  'test output')

        elif self.PASSED_RE.match(result_line):
            return

        else:
            raise error.TestError('Could not assert test success or failure, '
                                  'assuming failure. Please check debug logs')


    def run_once(self, test_dir, test_number):
        if test_number == '000':
            logging.debug('Dummy test to setup xfstests')
            return

        if test_number not in self._get_available_tests(test_dir):
            raise error.TestNAError(
                    'test file %s/%s not found' % (test_dir, test_number))

        test_name = os.path.join(test_dir, test_number)
        logging.debug("Running test: %s", test_name)
        self._run_sub_test(test_name)
