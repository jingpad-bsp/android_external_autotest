# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, shutil, tempfile

import cros_ui
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


class ChromeBinaryTest(test.test):
    """
    Base class for tests to run chrome test binaries without signing in and
    running Chrome.
    """

    CHROME_TEST_DEP = 'chrome_test'
    CHROME_SANDBOX = '/opt/google/chrome/chrome-sandbox'
    home_dir = None

    def setup(self):
        self.job.setup_dep([self.CHROME_TEST_DEP])


    def initialize(self):
        test_dep_dir = os.path.join(self.autodir, 'deps',
                                    self.CHROME_TEST_DEP)
        self.job.install_pkg(self.CHROME_TEST_DEP, 'dep', test_dep_dir)

        self.cr_source_dir = '%s/test_src' % test_dep_dir
        self.test_binary_dir = '%s/out/Release' % self.cr_source_dir
        self.home_dir = tempfile.mkdtemp()


    def cleanup(self):
        if self.home_dir:
            shutil.rmtree(self.home_dir, ignore_errors=True)


    def run_chrome_test_binary(self, binary_to_run, extra_params='', prefix='',
                               as_chronos=True):
        """
        Run chrome test binary.

        @param binary_to_run: The name of the browser test binary.
        @param extra_params: Arguments for the browser test binary.
        @param prefix: Prefix to the command that invokes the test binary.
        @param as_chronos: Boolean indicating if the tests should run in a
            chronos shell.

        @raises: error.TestFail if there is error running the command.
        """
        cmd = '%s/%s %s' % (self.test_binary_dir, binary_to_run, extra_params)
        env_vars = 'HOME=%s CR_SOURCE_ROOT=%s CHROME_DEVEL_SANDBOX=%s' % (
                self.home_dir, self.cr_source_dir, self.CHROME_SANDBOX)
        cmd = '%s %s' % (env_vars, prefix + cmd)

        try:
            if as_chronos:
                cros_ui.xsystem_as(cmd, user='chronos')
            else:
                cros_ui.xsystem(cmd)
        except error.CmdError as e:
            raise error.TestFail('%s failed! %s' % (binary_to_run, e))
