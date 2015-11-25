#!/usr/bin/python
# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import sys

import logging
# Turn the logging level to INFO before importing other autotest
# code, to avoid having failed import logging messages confuse the
# test_droid user.
logging.basicConfig(level=logging.INFO)

import common
from autotest_lib.site_utils import test_runner_utils


_TEST_REPORT_SCRIPTNAME = '/usr/bin/generate_test_report'


def parse_arguments(argv):
    """
    Parse command line arguments

    @param argv: argument list to parse

    @returns:    parsed arguments

    @raises SystemExit if arguments are malformed, or required arguments
            are not present.
    """
    return _parse_arguments_internal(argv)[0]


def _parse_arguments_internal(argv):
    """
    Parse command line arguments

    @param argv: argument list to parse

    @returns:    tuple of parsed arguments and argv suitable for remote runs

    @raises SystemExit if arguments are malformed, or required arguments
            are not present.
    """

    parser = argparse.ArgumentParser(description='Run remote tests.')

    parser.add_argument('serials', metavar='SERIALS',
                        help='Comma separate list of device serials under '
                             'test.')
    test_runner_utils.add_common_args(parser)
    return parser.parse_args(argv)


def main(argv):
    """
    Entry point for test_droid script.

    @param argv: arguments list
    """
    arguments = _parse_arguments_internal(argv)

    results_directory = test_runner_utils.create_results_directory(
            arguments.results_dir)
    arguments.results_dir = results_directory

    autotest_path = os.path.dirname(os.path.dirname(
            os.path.realpath(__file__)))
    site_utils_path = os.path.join(autotest_path, 'site_utils')
    realpath = os.path.realpath(__file__)
    site_utils_path = os.path.realpath(site_utils_path)
    host_attributes = {'serials' : arguments.serials,
                       'os_type' : 'android'}

    return test_runner_utils.perform_run_from_autotest_root(
                autotest_path, argv, arguments.tests, 'localhost',
                args=arguments.args, ignore_deps=not arguments.enforce_deps,
                results_directory=results_directory,
                iterations=arguments.iterations,
                fast_mode=arguments.fast_mode, debug=arguments.debug,
                host_attributes=host_attributes)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
