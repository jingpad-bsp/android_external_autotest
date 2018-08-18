# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Wrapper for running suites of tests and waiting for completion."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import sys

import logging

from lucifer import autotest
from skylab_suite import cros_suite
from skylab_suite import suite_parser
from skylab_suite import suite_runner
from skylab_suite import suite_tracking


PROVISION_SUITE_NAME = 'provision'


def _parse_suite_handler_spec(options):
    provision_num_required = 0
    if 'num_required' in options.suite_args:
        provision_num_required = options.suite_args['num_required']

    return cros_suite.SuiteHandlerSpec(
            suite_name=options.suite_name,
            wait=not options.create_and_return,
            suite_id=options.suite_id,
            timeout_mins=options.timeout_mins,
            passed_mins=options.passed_mins,
            test_retry=options.test_retry,
            max_retries=options.max_retries,
            use_fallback=options.use_fallback,
            provision_num_required=provision_num_required)


def _run_suite(options):
    run_suite_common = autotest.load('site_utils.run_suite_common')
    logging.info('Kicked off suite %s', options.suite_name)
    suite_spec = suite_parser.parse_suite_spec(options)
    if options.suite_name == PROVISION_SUITE_NAME:
        suite_job = cros_suite.ProvisionSuite(suite_spec)
    else:
        suite_job = cros_suite.Suite(suite_spec)

    try:
        suite_job.prepare()
    except Exception as e:
        logging.error('Infra failure in setting up suite job: %s', str(e))
        return run_suite_common.SuiteResult(
                run_suite_common.RETURN_CODES.INFRA_FAILURE)

    suite_handler_spec = _parse_suite_handler_spec(options)
    suite_handler = cros_suite.SuiteHandler(suite_handler_spec)
    suite_runner.run(suite_job.test_specs,
                     suite_handler,
                     options.dry_run)

    if options.create_and_return:
        suite_tracking.print_child_test_annotations(suite_handler)
        return run_suite_common.SuiteResult(run_suite_common.RETURN_CODES.OK)

    return_code = suite_tracking.log_suite_results(
                suite_job.suite_name, suite_handler)
    return run_suite_common.SuiteResult(return_code)


def parse_args():
    """Parse & validate skylab suite args."""
    parser = suite_parser.make_parser()
    options = parser.parse_args()
    if options.do_nothing:
        logging.info('Exit early because --do_nothing requested.')
        sys.exit(0)

    if not suite_parser.verify_and_clean_options(options):
        parser.print_help()
        sys.exit(1)

    return options


def main():
    """Entry point."""
    autotest.monkeypatch()

    options = parse_args()
    suite_tracking.setup_logging()
    result = _run_suite(options)
    logging.info('Will return from %s with status: %s',
                 os.path.basename(__file__), result.string_code)
    return result.return_code


if __name__ == "__main__":
    sys.exit(main())
