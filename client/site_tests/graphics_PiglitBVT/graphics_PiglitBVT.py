# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class graphics_PiglitBVT(test.test):
    """
    Runs a slice of the passing Piglit test sets.
    """
    version = 1

    test_scripts = 'test_scripts/'

    def run_once(self, test_slice):
        gpu_family = utils.get_gpu_family()
        family = gpu_family
        logging.info('Detected gpu family %s.', gpu_family)

        # TODO(ihf): Delete this once we have a piglit that runs on ARM.
        if gpu_family in ['mali', 'tegra']:
            logging.info('Not running any tests, passing by default.')
            return

        # We don't want to introduce too many combinations, so fall back.
        if not os.path.isdir(os.path.join(self.test_scripts, family)):
            family = 'other'
        logging.info('Using scripts for gpu family %s.', family)

        # Mark scripts executable if they are not.
        utils.system('chmod +x /usr/local/autotest/tests/graphics_PiglitBVT/' +
                     self.test_scripts + '*/graphics_PiglitBVT_*.sh')

        # Kick off test script.
        cmd = ('source /usr/local/autotest/tests/graphics_PiglitBVT/' +
               self.test_scripts +
               '%s/graphics_PiglitBVT_%d.sh' % (family, test_slice))
        logging.info('Executing cmd = %s', cmd)
        # TODO(ihf): See if we can get the test output in real time to the logs.
        # utils.run(cmd,
        #           stdout_tee=utils.TEE_TO_LOGS,
        #           stderr_tee=utils.TEE_TO_LOGS).stdout
        tests_failed = utils.system(cmd, ignore_status=True)
        if tests_failed:
            reason = '%d tests failed on "%s" in slice %d' % (tests_failed,
                                                              gpu_family,
                                                              test_slice)
            raise error.TestError(reason)
