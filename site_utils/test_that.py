#!/usr/bin/python
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import logging
import os
import subprocess
import sys

import common
try:
    from chromite.lib import cros_build_lib
except ImportError:
    print 'Unable to import chromite.'
    print 'This script must be either:'
    print '  - Be run in the chroot.'
    print '  - (not yet supported) be run after running '
    print '    ../utils/build_externals.py'

# first goal: reproduce the following use case:
# run_remote_test.sh --remote=<ip address of dut> suite:smoke


def ValidateArguments(arguments):
    """
    Validates parsed arguments.

    @param arguments: arguments object, as parsed by ParseArguments
    @raises: ValueError if arguments were invalid.
    """
    if arguments.args:
        raise ValueError('--args flag not yet supported.')

    if not arguments.board:
        raise ValueError('Board autodetection not yet supported. '
                         '--board required.')


def ParseArguments(argv):
    """
    Parse command line arguments

    @param argv: argument list to parse
    @returns:    parsed arguments.
    """
    parser = argparse.ArgumentParser(description='Run remote tests.')

    parser.add_argument('remote', metavar='REMOTE',
                        help='hostname[:port] for remote device. Specify '
                        ':lab: to run in test lab, or :vm:PORT_NUMBER to '
                        'run in vm.')
    parser.add_argument('tests', nargs='+', metavar='TEST',
                        help='Run given test(s). Use suite:SUITE to specify '
                        'test suite.')
    parser.add_argument('-b', '--board', metavar='BOARD',
                        action='store',
                        help='Board for which the test will run.')
    parser.add_argument('-i', '--build', nargs=1, metavar='BUILD',
                        help='Build to test. Device will be reimaged if '
                        'necessary. Omit flag to skip reimage and test '
                        'against already installed DUT image.')
    parser.add_argument('--args', nargs=1, metavar='ARGS',
                        help='Argument string to pass through to test.')

    return parser.parse_args(argv)


def main(argv):
    """
    Entry point for test_that script.
    @param argv: arguments list
    """
    if not cros_build_lib.IsInsideChroot():
        logging.error('Script must be invoked inside the chroot.')
        return 1

    arguments = ParseArguments(argv)
    try:
        ValidateArguments(arguments)
    except ValueError as err:
        logging.error('Invalid arguments. %s', err.message)
        return 1

    # TODO: Determine the following string programatically.
    # (same TODO applied to autotest_quickmerge)
    sysroot_path = os.path.join('/build', arguments.board, '')
    sysroot_autotest_path = os.path.join(sysroot_path, 'usr', 'local',
                                         'autotest', '')
    sysroot_site_utils_path = os.path.join(sysroot_autotest_path,
                                            'site_utils')

    if not os.path.exists(sysroot_path):
        logging.error('%s does not exist. Have you run setup_board?',
                      sysroot_path)
        return 1
    if not os.path.exists(sysroot_autotest_path):
        logging.error('%s does not exist. Have you run build_packages?',
                      sysroot_autotest_path)
        return 1

    # If we are not running the sysroot version of script, re-execute
    # that version of script with the same arguments.
    realpath = os.path.realpath(__file__)
    if os.path.dirname(realpath) != sysroot_site_utils_path:
        script_command = os.path.join(sysroot_site_utils_path,
                                      os.path.basename(realpath))
        return subprocess.call([script_command] + argv)

    print 'This script does not do anything yet.'
    print 'Reached end of execution for script %s with args %s.' % (realpath,
                                                                    argv)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))