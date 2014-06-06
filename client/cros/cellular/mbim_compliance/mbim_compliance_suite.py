#!/usr/bin/env python
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

import common
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_errors
from autotest_lib.client.cros.cellular.mbim_compliance import test_context
from autotest_lib.client.cros.cellular.mbim_compliance.tests import des_02_test


class MBIMComplianceSuite(object):
    """ Entry point into the MBIM compliance suite. """

    def __init__(self, continue_on_error=False):
        """
        @param continue_on_error: If True, the suite continues if there is an
                error in one of the tests. All errors raised are collated and
                raised together at the end.

        """
        self._continue_on_error = continue_on_error


    def run(self):
        """ Run the whole suite. """
        num_tests_failed = 0
        tests = self._get_all_tests()
        results = {}
        for test in tests:
            logging.debug('Running test: %s', test.name())
            try:
                test.run()
                logging.info('Test passed: %s', test.name())
                results[test.name()] = '[PASS]'
            except mbim_errors.MBIMComplianceError:
                num_tests_failed += 1
                results[test.name()] = '[FAIL]'
                if not self._continue_on_error:
                    raise

        self._report_results(results)
        if num_tests_failed > 0:
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceTestError,
                                      'MBIM Compliance suite failure. '
                                      '%d tests failed. See logs for details.' %
                                      num_tests_failed)


    def _get_all_tests(self):
        """
        Generate a list of tests to run.

        @returns: A list of tests to run.

        """
        return [
            des_02_test.DES_02_Test(test_context.TestContext())
        ]


    def _report_results(self, results):
        """
        Pretty-print the final result.

        @param results: A map of test name -> result.

        """
        width = max(len(x) for x in results.iterkeys()) + 6
        fmt = '{0:%d}{1}' % width
        logging.info('#### TEST RESULTS ####')
        for test, result in results.iteritems():
            logging.info(fmt.format(test, result))


def main():
    """ Entry function, if this module is run as a script. """
    logging.basicConfig(level=logging.DEBUG)
    mbim_suite = MBIMComplianceSuite()
    mbim_suite.run()


if __name__ == '__main__':
    main()
