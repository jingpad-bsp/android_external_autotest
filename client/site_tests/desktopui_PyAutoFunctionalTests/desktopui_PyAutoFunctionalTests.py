# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.cros import chrome_test


class desktopui_PyAutoFunctionalTests(chrome_test.PyAutoFunctionalTest):
    """Wrapper for running Chrome's PyAuto-based functional tests."""
    version = 1


    def run_once(self, suite='', tests=[]):
        """Run pyauto functional tests.

        Args:
            suite: string corresponding to the pyauto functional suite to run.
            tests: list of tests to run.

        Either suite or tests should be specified, not both.
        """
        self.run_pyauto_functional(suite=suite, tests=tests)
