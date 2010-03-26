# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dircache, logging, os, utils, time
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

TPM_TSS_VERSION = "1.2"
TPM_OWNER_SECRET = "owner123"
TPM_SRK_SECRET = "srk123"

def run_trousers_tests(bindir):
        # Special return codes from trousers tests.
        TEST_RETURN_SUCCESS = 0
        TEST_RETURN_NOT_IMPLEMENTED = 6
        TEST_RETURN_NOT_APPLICABLE = 126

        num_tests_considered = 0
        num_tests_passed = 0
        num_tests_failed = 0
        num_tests_not_implemented = 0
        num_tests_not_applicable = 0

        os.putenv('TESTSUITE_OWNER_SECRET', TPM_OWNER_SECRET)
        os.putenv('TESTSUITE_SRK_SECRET', TPM_SRK_SECRET)

        for test in dircache.listdir(bindir):
            logging.info('Running test: %s' % test)
            num_tests_considered = num_tests_considered + 1
            return_code = utils.system('%s/%s -v %s' %
                                       (bindir, test, TPM_TSS_VERSION),
                                       timeout=180,  # In seconds
                                       ignore_status=True  # Want return code
                                       )
            logging.info('-- Return code: %d (%s)' % (return_code, test))
            if return_code == TEST_RETURN_SUCCESS:
                num_tests_passed = num_tests_passed + 1
            elif return_code == TEST_RETURN_NOT_IMPLEMENTED:
                num_tests_not_implemented = num_tests_not_implemented + 1
            elif return_code == TEST_RETURN_NOT_APPLICABLE:
                num_tests_not_applicable = num_tests_not_applicable + 1
            else:
                num_tests_failed = num_tests_failed + 1

        logging.info('Considered %d tests.' % num_tests_considered)
        logging.info('-- Passed: %d' % num_tests_passed)
        logging.info('-- Failed: %d' % num_tests_failed)
        logging.info('-- Not Implemented: %d' % num_tests_not_implemented)
        logging.info('-- Not Applicable: %d' % num_tests_not_applicable)

        if num_tests_failed != 0:
            raise error.TestError('Test failed (%d failures)' %
                                  num_tests_failed)
