# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os

import dateutil.parser

from autotest_lib.client.common_lib import base_job
from autotest_lib.client.common_lib import error
from autotest_lib.server import test
from autotest_lib.server import utils


# A datetime.DateTime representing the Unix epoch in UTC.
_UNIX_EPOCH = dateutil.parser.parse('1970-01-01T00:00:00Z')


class tast_Runner(test.test):
    """Autotest server test that runs a Tast test suite.

    Tast is an integration-testing framework analagous to the test-running
    portion of Autotest. See
    https://chromium.googlesource.com/chromiumos/platform/tast/ for more
    information.

    This class runs the "tast" command locally to execute a Tast test suite on a
    remote DUT.
    """
    version = 1

    # Maximum time to wait for the tast command to complete, in seconds.
    _EXEC_TIMEOUT_SEC = 600

    # JSON file written by the tast command containing test results.
    _RESULTS_FILENAME = 'results.json'

    # Maximum number of failing tests to include in error message.
    _MAX_TEST_NAMES_IN_ERROR = 3

    # Default paths where Tast files are installed.
    _TAST_PATH = '/usr/bin/tast'
    _REMOTE_BUNDLE_DIR = '/usr/libexec/tast/bundles/remote'
    _REMOTE_DATA_DIR = '/usr/share/tast/data/remote'
    _REMOTE_TEST_RUNNER_PATH = '/usr/bin/remote_test_runner'

    # When Tast is deployed from CIPD packages in the lab, it's installed under
    # this prefix rather than under the root directory.
    _CIPD_INSTALL_ROOT = '/opt/infra-tools'

    # Prefix added to Tast test names when writing their results to TKO
    # status.log files.
    _TEST_NAME_PREFIX = 'tast_Runner.'

    # Job start/end TKO event status codes from base_client_job._rungroup in
    # client/bin/job.py.
    _JOB_STATUS_START = 'START'
    _JOB_STATUS_END_GOOD = 'END GOOD'
    _JOB_STATUS_END_FAIL = 'END FAIL'
    _JOB_STATUS_END_ABORT = 'END ABORT'

    # In-job TKO event status codes from base_client_job._run_test_base in
    # client/bin/job.py and client/common_lib/error.py.
    _JOB_STATUS_GOOD = 'GOOD'
    _JOB_STATUS_FAIL = 'FAIL'

    def initialize(self, host, test_exprs, report_tests=True):
        """
        @param host: remote.RemoteHost instance representing DUT.
        @param test_exprs: Array of strings describing tests to run.
        @param report_tests: If True, report individual Tast tests' results in
            status.log.

        @raises error.TestFail if the Tast installation couldn't be found.
        """
        self._host = host
        self._test_exprs = test_exprs
        self._report_tests = report_tests

        # List of JSON objects corresponding to tests from a Tast results.json
        # file. See TestResult in
        # src/platform/tast/src/chromiumos/cmd/tast/run/results.go for details.
        self._test_results = []

        # The data dir can be missing if no remote tests registered data files,
        # but all other files must exist.
        self._tast_path = self._get_path(self._TAST_PATH)
        self._remote_bundle_dir = self._get_path(self._REMOTE_BUNDLE_DIR)
        self._remote_data_dir = self._get_path(self._REMOTE_DATA_DIR,
                                               allow_missing=True)
        self._remote_test_runner_path = self._get_path(
                self._REMOTE_TEST_RUNNER_PATH)

    def run_once(self):
        """Runs the test suite once."""
        self._log_version()
        self._run_tast()
        self._parse_results()

    def _get_path(self, path, allow_missing=False):
        """Returns the path to an installed Tast-related file or directory.

        @param path Absolute path in root filesystem, e.g. "/usr/bin/tast".
        @param allow_missing True if it's okay for the path to be missing.

        @return: Absolute path within install root, e.g.
            "/opt/infra-tools/usr/bin/tast", or an empty string if the path
            wasn't found and allow_missing is True.

        @raises error.TestFail if the path couldn't be found and allow_missing
            is False.
        """
        if os.path.exists(path):
            return path

        cipd_path = os.path.join(self._CIPD_INSTALL_ROOT,
                                 os.path.relpath(path, '/'))
        if os.path.exists(cipd_path):
            return cipd_path

        if allow_missing:
            return ''
        raise error.TestFail('Neither %s nor %s exists' % (path, cipd_path))

    def _log_version(self):
        """Runs the tast command locally to log its version."""
        try:
            utils.run([self._tast_path, '-version'],
                      timeout=self._EXEC_TIMEOUT_SEC,
                      stdout_tee=utils.TEE_TO_LOGS,
                      stderr_tee=utils.TEE_TO_LOGS,
                      stderr_is_expected=True,
                      stdout_level=logging.INFO,
                      stderr_level=logging.ERROR)
        except error.CmdError as e:
            logging.error('Failed to log tast version: %s' % str(e))

    def _run_tast(self):
        """Runs the tast command locally to perform testing against the DUT.

        @raises error.TestFail if the tast command fails or times out (but not
            if individual tests fail).
        """
        cmd = [
            self._tast_path,
            '-verbose',
            '-logtime=false',
            'run',
            '-build=false',
            '-resultsdir=' + self.resultsdir,
            '-remotebundledir=' + self._remote_bundle_dir,
            '-remotedatadir=' + self._remote_data_dir,
            '-remoterunner=' + self._remote_test_runner_path,
            self._host.hostname,
        ]
        cmd.extend(self._test_exprs)

        logging.info('Running ' +
                     ' '.join([utils.sh_quote_word(a) for a in cmd]))
        try:
            utils.run(cmd,
                      ignore_status=False,
                      timeout=self._EXEC_TIMEOUT_SEC,
                      stdout_tee=utils.TEE_TO_LOGS,
                      stderr_tee=utils.TEE_TO_LOGS,
                      stderr_is_expected=True,
                      stdout_level=logging.INFO,
                      stderr_level=logging.ERROR)
        except error.CmdError as e:
            raise error.TestFail('Failed to run tast: %s' % str(e))
        except error.CmdTimeoutError as e:
            raise error.TestFail('Got timeout while running tast: %s' % str(e))

    def _parse_results(self):
        """Parses results written by the tast command.

        @raises error.TestFail if one or more tests failed.
        """
        # Register a hook to write the results of individual Tast tests as
        # top-level entries in the TKO status.log file.
        if self._report_tests:
            self.job.add_post_run_hook(self._log_all_tests)

        path = os.path.join(self.resultsdir, self._RESULTS_FILENAME)
        failed = []
        with open(path, 'r') as f:
            for test in json.load(f):
                self._test_results.append(test)
                if test['errors']:
                    name = test['name']
                    for err in test['errors']:
                        logging.warning('%s: %s', name, err['reason'])
                    # TODO(derat): Report failures in flaky tests in some other
                    # way.
                    if 'flaky' not in test.get('attr', []):
                        failed.append(name)

        if failed:
            msg = '%d failed: ' % len(failed)
            msg += ' '.join(sorted(failed)[:self._MAX_TEST_NAMES_IN_ERROR])
            if len(failed) > self._MAX_TEST_NAMES_IN_ERROR:
                msg += ' ...'
            raise error.TestFail(msg)

    def _log_all_tests(self):
        """Writes entries to the TKO status.log file describing the results of
        all tests.
        """
        for test in self._test_results:
            self._log_test(test)

    def _log_test(self, test):
        """Writes events to the TKO status.log file describing the results from
        a Tast test.

        @param test: A JSON object corresponding to a single test from a Tast
            results.json file. See TestResult in
            src/platform/tast/src/chromiumos/cmd/tast/run/results.go for
            details.
        """
        name = self._TEST_NAME_PREFIX + test['name']
        start_time = _rfc3339_time_to_timestamp(test['start'])
        end_time = _rfc3339_time_to_timestamp(test['end'])

        self._log_test_event(self._JOB_STATUS_START, name, start_time)

        if not test['errors']:
            self._log_test_event(self._JOB_STATUS_GOOD, name, end_time)
            end_status = self._JOB_STATUS_END_GOOD
        else:
            # The previous START event automatically increases the log
            # indentation level until the following END event.
            for err in test['errors']:
                # TODO(derat): Tast doesn't current report timestamps associated
                # with test errors, but it should -- the test doesn't
                # necessarily halt in response to the first error.
                self._log_test_event(self._JOB_STATUS_FAIL, name, end_time,
                                     err['reason'])
            end_status = self._JOB_STATUS_END_FAIL

        self._log_test_event(end_status, name, end_time)

    def _log_test_event(self, status_code, test_name, timestamp, message=''):
        """Logs a single event to the TKO status.log file.

        @param status_code: Event status code, e.g. 'END GOOD'. See
            client/common_lib/log.py for accepted values.
        @param test_name: Tast test name, e.g. 'ui.ChromeSanity'.
        @param timestamp: Event timestamp (as seconds since Unix epoch).
        @param message: Optional human-readable message.
        """
        # The TKO parser code chokes on floating-point timestamps.
        entry = base_job.status_log_entry(status_code, None, test_name, message,
                                          None, timestamp=int(timestamp))
        self.job.record_entry(entry, False)


def _rfc3339_time_to_timestamp(time_str):
    """Converts an RFC3339 time into a Unix timestamp.

    @param time_str: RFC3339-compatible time, e.g.
        '2018-02-25T07:45:35.916929332-07:00'.

    @returns Float number of seconds since the Unix epoch.
    """
    return (dateutil.parser.parse(time_str) - _UNIX_EPOCH).total_seconds()
