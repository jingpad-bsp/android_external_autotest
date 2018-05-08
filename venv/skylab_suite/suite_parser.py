# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Parse & Validate CLI arguments for run_suite_skylab.py."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse

from autotest_lib.client.common_lib import priorities


def make_parser():
    """Make ArgumentParser instance for run_suite_skylab.py."""
    parser = argparse.ArgumentParser(prog='run_suite_skylab',
                                     description=__doc__)

    # Suite-related parameters.
    parser.add_argument('--board', required=True)
    parser.add_argument(
            '--model',
            help=('The device model to run tests against. For non-unified '
                  'builds, model and board are synonymous, but board is more '
                  'accurate in some cases. Only pass this option if your build '
                  'is a unified build.'))
    parser.add_argument(
        '--pool', default='suites',
        help=('Specify the pool of DUTs to run this suite. If you want no '
              'pool, you can specify it with --pool="". USE WITH CARE.'))
    parser.add_argument(
        '--suite_name', required=True,
        help='Specify the suite to run.')
    parser.add_argument(
        '--build', required=True,
        help='Specify the build to run the suite with.')
    parser.add_argument(
        '--cheets_build', default=None,
        help='ChromeOS Android build to be installed on dut.')
    parser.add_argument(
        '--firmware_rw_build', default=None,
        help='Firmware build to be installed in dut RW firmware.')
    parser.add_argument(
        '--firmware_ro_build', default=None,
        help='Firmware build to be installed in dut RO firmware.')
    parser.add_argument(
        '--test_source_build', default=None,
        help=('Build that contains the test code. It can be the value '
              'of arguments "--build", "--firmware_rw_build" or '
              '"--firmware_ro_build". Default is to use test code from '
              'the "--build" version (CrOS image)'))
    parser.add_argument(
        '--priority', type=int, default=priorities.Priority.values[0],
        choices=priorities.Priority.values,
        help=('The priority to run the suite. A smaller value means this suite '
              'will be executed in a low priority, e.g. being delayed to '
              'execute. Each numerical value represents: '+ ', '.join([
                  '(%s: %s)' % (str(v), n) for v, n in
                  zip(priorities.Priority.values, priorities.Priority.names)])))

    # Swarming-related parameters.
    parser.add_argument(
        '--swarming', default=None,
        help='The swarming server to call.')
    parser.add_argument(
        '--execution-timeout-seconds', type=int, default=30,
        help='Seconds to allow a task to complete, once execution beings.')

    # logic-related parameters.
    parser.add_argument(
        '--create-and-return', action='store_true',
        help='Create the child jobs of a suite, then finish immediately.')
    parser.add_argument(
        '--max-retries', default=0, type=int, action='store',
        help='Maximum retries allowed at suite level. No retry if it is 0.')
    parser.add_argument(
        '--json_dump', action='store_true', default=False,
        help='Dump the output of run_suite to stdout.')
    parser.add_argument(
        '--run-prod-code', action='store_true', default=False,
        help='Run the test code that lives in prod aka the test '
        'code currently on the lab servers.')
    parser.add_argument(
        '--dry_run', action='store_true',
        help=('Used for kicking off a run of suite with fake commands.'))
    parser.add_argument(
        '--do_nothing', action='store_true',
        help=('Used for monitoring purposes, to measure no-op swarming proxy '
              'latency or create a dummy run_suite_skylab run.'))

    return parser


def verify_and_clean_options(options):
    """Validate options."""
    return True
