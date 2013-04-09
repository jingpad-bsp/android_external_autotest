# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import site_utils

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

        # find paths for touchpad tests
        root = os.path.join(self.autodir, 'deps', 'touchpad-tests')
        framework_dir = os.path.join(root, 'framework')
        tests_dir = os.path.join(root, 'tests')
        xorg_dir = os.path.join(root, 'xorg-conf-files')

        # create test runner
        sys.path.append(framework_dir)
        from test_runner import TestRunner
        runner = TestRunner(tests_dir, xorg_dir)

        # run all tests for this board and extract results
        results = runner.RunAll('%s*/*' % board)
        self.test_results = {}
        for key, value in results.items():
            self.test_results[key.replace('/', '-')] = value["score"]

        # write converted test results out
        if self.test_results:
            self.write_perf_keyval(self.test_results)
