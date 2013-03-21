# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error, site_utils

#  Parse the score result lines, e.g. output of regression tests for mario
#
#  | mario/base_click   |          |  success (1.0000)  |         |
#  | mario/base_tap     |          |  failure           |         |
#
#  We would like to retrieve the test name and its score if it is a success
#  pattern and give the score of 0.0 if it is a failure pattern.
SUCCESS_PATTERN = '\|\s*([\w\d.]*/\w+)\s*\|\s*\|\s*\w+\s\((\d.\d+)\)\s*\|'
SUCCESS_RE = re.compile(SUCCESS_PATTERN)
FAILURE_PATTERN = '\|\s*([\w\d.]*/\w+)\s*\|\s*\|\s*failure\s*\|'
FAILURE_RE = re.compile(FAILURE_PATTERN)
TOUCHPAD_TEST = os.path.join('touchpad-tests', 'touchtests')


class platform_GesturesRegressionTest(test.test):
    """ Wrapper of regression test of gestures library.

    This test takes advantage of autotest framework to execute the touchtests,
    i.e. regression test of gestures library, and store results of the test
    per build(as one of BVTs) for us to keep track of patches of gestures
    library and regression tests, and their score changes accordingly.
    """
    version = 1

    def setup(self):
        self.job.setup_dep(['touchpad-tests'])

    def run_once(self):
        """ Run the regression test and collect the results.
        """
        # decide what tests to be executed, strip out prefix 'x86-' if exists
        board = site_utils.get_current_board().replace('x86-', '')
        if board == 'daisy':
            board = 'snow'

        touchtests = os.path.join(self.autodir, 'deps', TOUCHPAD_TEST)
        cmd = '%s --autotest %s*/*' % (touchtests, board)
        output = utils.system_output(cmd)
        if not output:
            raise error.TestError('Can not run the touchtests')

        self.test_results = {}
        for line in output.splitlines():
            result = SUCCESS_RE.search(line)
            score = ''
            if result:
                score = result.group(2)
            else:
                result = FAILURE_RE.search(line)
                if result:
                    # set the score of failure test to 0.0
                    score = '0.0'
            if score:
                # '/' is not a valid character for a key name
                self.test_results[result.group(1).replace('/', '-')] = score
        # write converted test results out
        if self.test_results:
            self.write_perf_keyval(self.test_results)
