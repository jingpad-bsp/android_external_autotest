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
from skylab_suite import dynamic_suite
from skylab_suite import suite_parser
from skylab_suite import suite_tracking


PROVISION_SUITE_NAME = 'provision'


def _parse_suite_specs(options):
    suite_common = autotest.load('server.cros.dynamic_suite.suite_common')
    builds = suite_common.make_builds_from_options(options)
    return cros_suite.SuiteSpecs(
            builds=builds,
            suite_name=options.suite_name,
            suite_file_name=suite_common.canonicalize_suite_name(
                    options.suite_name),
            test_source_build=suite_common.get_test_source_build(
                    builds, test_source_build=options.test_source_build),
            suite_args=options.suite_args,
            timeout_mins=options.timeout_mins,
    )


def _run_suite(options):
    logging.info('Kicked off suite %s', options.suite_name)
    suite_specs = _parse_suite_specs(options)
    if options.suite_name == PROVISION_SUITE_NAME:
        suite_job = cros_suite.ProvisionSuite(suite_specs)
    else:
        suite_job = cros_suite.Suite(suite_specs)

    suite_job.prepare()
    dynamic_suite.run(suite_job, options.dry_run)
    return suite_tracking.SuiteResult(
                suite_tracking.SUITE_RESULT_CODES.OK)


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

    if options.json_dump:
        suite_tracking.dump_json(result)

    logging.info('Will return from %s with status: %s',
                 os.path.basename(__file__), result.string_code)


if __name__ == "__main__":
    main()
