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
import re

from autotest_lib.client.common_lib import error
from autotest_lib.server import utils
from autotest_lib.server.cros import tradefed_test

_PARTNER_GTS_LOCATION = 'gs://chromeos-partner-gts/gts-4.1_r1-3556119.zip'


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

        self.waivers = self._get_expected_failures('expectations')


    def _run_gts_tradefed(self, target_package):
        """This tests runs the GTS(XTS) tradefed binary and collects results.

        @param target_package: the name of test package to be run. If None is
                set, full GTS set will run.
        @raise TestFail: when a test failure is detected.
        """
        self._target_package = target_package
        gts_tradefed = os.path.join(
                self._android_gts,
                'android-gts',
                'tools',
                'gts-tradefed')
        logging.info('GTS-tradefed path: %s', gts_tradefed)
        #TODO(dhaddock): remove --skip-device-info with GTS 4.1_r2 (b/32889514)
        gts_tradefed_args = ['run', 'commandAndExit', 'gts',
                             '--skip-device-info', '--module',
                             self._target_package]
        # Run GTS via tradefed and obtain stdout, sterr as output.
        with tradefed_test.adb_keepalive(self._get_adb_target(),
                                         self._install_paths):
            output = self._run(
                    gts_tradefed,
                    args=gts_tradefed_args,
                    verbose=True,
                    # Make sure to tee tradefed stdout/stderr to autotest logs
                    # already during the test run.
                    stdout_tee=utils.TEE_TO_LOGS,
                    stderr_tee=utils.TEE_TO_LOGS)
        result_destination = os.path.join(self.resultsdir, 'android-gts')

        # Gather the global log first. Datetime parsing below can abort the test
        # if tradefed startup had failed. Even then the global log is useful.
        self._collect_tradefed_global_log(output, result_destination)

        # Parse stdout to obtain datetime IDs of directories into which tradefed
        # wrote result xml files and logs.
        datetime_id = self._parse_tradefed_datetime(output)
        repository = os.path.join(self._android_gts, 'android-gts')
        self._collect_logs(repository, datetime_id, result_destination)

        # Result parsing must come after all other essential operations as test
        # warnings, errors and failures can be raised here.
        tests, passed, failed, not_executed = self._parse_result(output,
                                                                 self.waivers)
        if tests != passed or failed > 0 or not_executed > 0:
            raise error.TestFail('Failed: Passed (%d), Failed (%d), '
                                 'Not Executed (%d)' %
                                 (passed, failed, not_executed))

        # All test has passed successfully, here.
        logging.info('The test has passed successfully.')

    def _parse_tradefed_datetime(self, result):
        """This parses the tradefed datetime object from the GTS output.
        :param result: the tradefed result object
        :return: the datetime
        """
        #TODO(dhaddock): Merge this into tradefed_test when N is working
        match = re.search(r': Starting invocation for .+ (\S+) on device',
                          result.stdout)
        datetime_id = match.group(1)
        logging.info('Tradefed identified results and logs with %s.',
                     datetime_id)
        return datetime_id

    def _parse_result(self, result, waivers=None):
        """Check the result from the tradefed output.

        This extracts the test pass/fail/executed list from the output of
        tradefed. It is up to the caller to handle inconsistencies.

        @param result: The result object from utils.run.
        @param waivers: a set() of tests which are permitted to fail.
        """
        # TODO(dhaddock): This function overrides the parent version while GTS
        # uses the updated version with modules and new output.
        # This will be merged into the tradefed_test.py class eventually.
        match = re.search(r': Invocation finished in (.*). PASSED: (\d+), '
                          r'FAILED: (\d+), '
                          r'NOT EXECUTED: (\d+), MODULES: ('
                          r'\d+) of (\d+)', result.stdout)

        if not match:
            raise error.Test('Test log does not contain a summary.')

        passed = int(match.group(2))
        failed = int(match.group(3))
        not_executed = int(match.group(4))

        # Some tests may be split into several groups. E.g. per architecture as
        # follows;
        #   Starting x86 GtsAccountsHostTestCases with 3 tests
        #   Starting armeabi-v7a GtsAccountsHostTestCases with 3 tests
        group_list = re.findall(r'Starting (.+) %s with (\d+(?:,\d+)?) tests' %
                                self._target_package,
                                result.stdout)

        abis = []
        if group_list:
            tests = sum(int(num_tests[1].replace(',', ''))
                        for num_tests in group_list)
            abis = [abi[0] for abi in group_list]
        else:
            # Unfortunately this happens. Assume it made no other mistakes.
            logging.warning('Tradefed forgot to print number of tests.')
            tests = passed + failed + not_executed
        # TODO(rohitbm): make failure parsing more robust by extracting the list
        # of failing tests instead of searching in the result blob.
        if waivers:
            for testname in waivers:
                fail_count = result.stdout.count(testname + ' fail')
                if fail_count:
                    # For arm only, we repeat the test cases with output like
                    # Starting armeabi-v7a GtsPlacementTestCases with 12 tests
                    # Continuing armeabi-v7a GtsPlacementTestcase with 12 tests
                    if abis == ['armeabi-v7a']:
                        fail_count /= 2
                    if fail_count > len(abis):
                        raise error.TestFail('Error: Found %d failures for %s '
                                             'but there are only %d abis: %s' %
                                             (fail_count, testname, len(abis),
                                             abis))
                    failed -= fail_count
                    # To maintain total count consistency.
                    passed += fail_count
                    logging.info('Waived failure for %s %d time(s)',
                                 testname, fail_count)
        logging.info('tests=%d, passed=%d, failed=%d, not_executed=%d',
                     tests, passed, failed, not_executed)
        if failed < 0:
            raise error.TestFail('Error: Internal waiver book keeping has '
                                 'become inconsistent.')
        return (tests, passed, failed, not_executed)

    def run_once(self, target_package=None):
        """Runs GTS target package exactly once."""
        with self._login_chrome():
            self._connect_adb()
            self._disable_adb_install_dialog()
            self._wait_for_arc_boot()
            self._run_gts_tradefed(target_package)
