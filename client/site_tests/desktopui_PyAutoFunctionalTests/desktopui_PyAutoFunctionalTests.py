# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import utils
from autotest_lib.client.cros import chrome_test, cros_ui


class desktopui_PyAutoFunctionalTests(chrome_test.ChromeTestBase):
    """Wrapper for running Chrome's PyAuto-based functional tests.

    Performs all setup and fires off the FULL suite.
    """

    version = 1

    def initialize(self, auto_login):
        # Control whether we want to auto login
        # (auto_login is defined in cros_ui_test.py)
        self.auto_login = auto_login
        chrome_test.ChromeTestBase.initialize(self)


    def run_once(self, suite=None, tests=None):
        """Run pyauto functional tests.

        Args:
            suite: the pyauto functional suite to run.
            tests: the test modules to run.

        Either suite or tests should be specified, not both.
        """
        assert suite or tests, 'Should specify suite or tests'
        assert not (suite and tests), \
            'Should specify either suite or tests, not both'

        deps_dir = os.path.join(self.autodir, 'deps')

        # Run tests.
        functional_cmd = 'python %s/chrome_test/test_src/' \
            'chrome/test/functional/pyauto_functional.py -v ' % deps_dir
        if suite:
            functional_cmd += ' --suite=%s' % suite
        elif tests:
            functional_cmd += tests

        launch_cmd = cros_ui.xcommand(functional_cmd)
        print 'Test launch cmd', launch_cmd
        utils.system(launch_cmd)

