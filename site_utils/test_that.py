#!/usr/bin/python
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import sys

import common

# first goal: reproduce the following use case:
# run_remote_test.sh --remote=<ip address of dut> suite:smoke


def ParseArguments(argv):
    """
    Parse command line arguments

    @param argv: argument list to parse
    @returns:    parsed arguments.
    """
    parser = argparse.ArgumentParser(description='Run remote tests.')

    parser.add_argument('remote', nargs=1, metavar='REMOTE',
                        help='hostname[:port] for remote device. Specify '
                        ':lab: to run in test lab, or :vm:PORT_NUMBER to '
                        'run in vm.')
    parser.add_argument('tests', nargs='+', metavar='TEST',
                        help='Run given test(s). Use suite:SUITE to specify '
                        'test suite.')
    parser.add_argument('-b', '--board', nargs=1, metavar='BOARD',
                        help='Board for which the test will run.')
    parser.add_argument('-i', '--build', nargs=1, metavar='BUILD',
                        help='Build to test. Device will be reimaged if '
                        'necessary. Omit flag to skip reimage and test '
                        'against already installed DUT image.')
    parser.add_argument('--args', nargs='?', metavar='ARGS',
                        help='Argument string to pass through to test.')

    return parser.parse_args(argv)


def main(argv):
    """
    Entry point for test_that script.
    @param argv: arguments list
    """
    arguments = ParseArguments(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))