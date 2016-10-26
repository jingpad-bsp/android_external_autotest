# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# repohooks/pre-upload.py currently does not run pylint. But for developers who
# want to check their code manually we disable several harmless pylint warnings
# which just distract from more serious remaining issues.
#
# The instance variable _android_gts is not defined in __init__().
# pylint: disable=attribute-defined-outside-init
#
# Many short variable names don't follow the naming convention.
# pylint: disable=invalid-name

import logging
import os

from autotest_lib.client.common_lib import error
from autotest_lib.server import utils
from autotest_lib.server.cros import tradefed_test

_PARTNER_GTS_LOCATION = 'gs://chromeos-partner-gts/android-gts-3.0r6.zip'


class cheets_GTS(tradefed_test.TradefedTest):
    """Sets up tradefed to run GTS tests."""
    version = 1

    def setup(self, uri=None):
        """Set up GTS bundle from Google Storage.

        @param uri: The location to pull the GTS bundle from.
        """

        if uri:
            self._android_gts = self._install_bundle(uri)
        else:
            self._android_gts = self._install_bundle(_PARTNER_GTS_LOCATION)

    def _run_gts_tradefed(self, target_package):
        """This tests runs the GTS(XTS) tradefed binary and collects results.

        @param target_package: the name of test package to be run. If None is
                set, full GTS set will run.
        @raise TestFail: when a test failure is detected.
        """
        gts_tradefed = os.path.join(
                self._android_gts,
                'android-xts',
                'tools',
                'xts-tradefed')
        logging.info('GTS-tradefed path: %s', gts_tradefed)
        gts_tradefed_args = [
                'run', 'xts', '--package', target_package,
                '--result-server=https://cts.googleplex.com/results/uploadUrl']
        # Run GTS via tradefed and obtain stdout, sterr as output.
        output = self._run(
                gts_tradefed,
                args=gts_tradefed_args,
                verbose=True,
                # Make sure to tee tradefed stdout/stderr to autotest logs
                # already during the test run.
                stdout_tee=utils.TEE_TO_LOGS,
                stderr_tee=utils.TEE_TO_LOGS)
        # Parse stdout to obtain datetime IDs of directories into which tradefed
        # wrote result xml files and logs.
        datetime_id = self._parse_tradefed_datetime(output)
        repository = os.path.join(self._android_gts, 'android-xts',
                'repository')
        autotest = os.path.join(self.resultsdir, 'android-xts')
        self._collect_logs(repository, datetime_id, autotest)
        # Result parsing must come after all other essential operations as test
        # warnings, errors and failures can be raised here.
        tests, passed, failed, not_executed = self._parse_result(output)
        if tests != passed or failed > 0 or not_executed > 0:
            raise error.TestFail('Passed (%d), Failed (%d), Not Executed ('
                                 '%d)' % (passed, failed, not_executed))

        # All test has passed successfully, here.
        logging.info('The test has passed successfully.')

    def run_once(self, target_package=None):
        """Runs GTS target package exactly once."""
        with self._login_chrome():
            self._connect_adb()
            self._disable_adb_install_dialog()
            self._wait_for_arc_boot()
            self._run_gts_tradefed(target_package)
