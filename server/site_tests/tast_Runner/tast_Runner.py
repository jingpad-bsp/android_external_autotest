# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os

from autotest_lib.client.common_lib import error
from autotest_lib.server import test
from autotest_lib.server import utils


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

    def initialize(self, host, test_exprs):
        """
        @param host: remote.RemoteHost instance representing DUT.
        @param test_exprs: Array of strings describing tests to run.
        """
        self._host = host
        self._test_exprs = test_exprs

    def run_once(self):
        """Runs the test suite once."""
        self._run_tast()
        self._parse_results()

    def _run_tast(self):
        """Runs the tast command locally to perform testing against the DUT."""
        cmd = ['tast', '-verbose', '-logtime=false', 'run', '-build=false']
        cmd.append('-resultsdir=' + self.resultsdir)
        cmd.append(self._host.hostname)
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
        path = os.path.join(self.resultsdir, self._RESULTS_FILENAME)
        failed = []
        with open(path, 'r') as f:
            for test in json.load(f):
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
