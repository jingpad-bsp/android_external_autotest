# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import utils
from autotest_lib.client.cros import chrome_test, cros_ui, ownership


class desktopui_PyAutoFunctionalTests(chrome_test.ChromeTestBase):
    """Wrapper for running Chrome's PyAuto-based functional tests.

    Performs all setup and fires off the FULL suite.
    """

    version = 1


    def initialize(self):
        chrome_test.ChromeTestBase.initialize(self)
        self.setup_for_pyauto()


    def run_once(self, suite=None, tests=None, auto_login=True):
        """Run pyauto functional tests.

        Args:
            suite: the pyauto functional suite to run.
            tests: the test modules to run.
            auto_login: if True, login to default account before firing off.

        Either suite or tests should be specified, not both.
        """
        assert suite or tests, 'Should specify suite or tests'
        assert not (suite and tests), \
            'Should specify either suite or tests, not both'

        deps_dir = os.path.join(self.autodir, 'deps')
        if auto_login:
            # Enable chrome testing interface and Login.
            pyautolib_dir = os.path.join(self.cr_source_dir,
                                         'chrome', 'test', 'pyautolib')
            login_cmd = cros_ui.xcommand_as(
                'python %s chromeos_utils.ChromeosUtils.LoginToDefaultAccount '
                '-v --no-http-server' % os.path.join(
                    pyautolib_dir, 'chromeos', 'chromeos_utils.py'))
            print 'Login cmd', login_cmd
            utils.system(login_cmd)

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


    def cleanup(self):
        ownership.clear_ownership()
        chrome_test.ChromeTestBase.cleanup(self)
