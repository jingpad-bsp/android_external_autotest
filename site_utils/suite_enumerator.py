#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool for enumerating the tests in a given suite.

Given an autotest root directory and a suite name (e.g., bvt, regression), this
tool will print out the name of each test in that suite, one per line.

Example:
$ ./site_utils/suite_enumerator.py -a /usr/local/autotest bvt 2>/dev/null
login_LoginSuccess
logging_CrashSender
login_BadAuthentication

This is intended for use only with Chrome OS test suits that leverage the
dynamic suite infrastructure in server/cros/dynamic_suite.py.
"""

import optparse, os, sys, time
import common
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.server.cros.dynamic_suite import control_file_getter
from autotest_lib.server.cros.dynamic_suite.suite import Suite

def parse_options():
    usage = "usage: %prog [options] suite_name"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('-a', '--autotest_dir', dest='autotest_dir',
                      default=os.path.abspath(
                          os.path.join('..', os.path.dirname(__file__))),
                      help='Directory under which to search for tests.'\
                           ' (e.g. /usr/local/autotest)')
    parser.add_option('-s', '--stable_only', dest='add_experimental',
                      action='store_false', default=True,
                      help='List only tests that are not labeled experimental.')
    parser.add_option('-l', '--listall',
                      action='store_true', default=False,
                      help='Print a listing of all suites. Ignores all args.')
    options, args = parser.parse_args()
    return parser, options, args


def main():
    parser, options, args = parse_options()
    if options.listall:
        if args:
            print 'Cannot use suite_name with --listall'
            parser.print_help()
    elif not args or len(args) != 1:
        parser.print_help()
        return

    fs_getter = Suite.create_fs_getter(options.autotest_dir)
    devserver = dev_server.ImageServer('')
    if options.listall:
        for suite in Suite.list_all_suites('', devserver, fs_getter):
            print suite
        return

    suite = Suite.create_from_name(args[0], '', devserver, fs_getter)
    # If in test list, print firmware_FAFTSetup before other tests
    # NOTE: the test.name value can be *different* from the directory
    # name that appears in test.path
    PRETEST_LIST = ['firmware_FAFTSetup',]
    for test in filter(lambda test: test.name in \
                              PRETEST_LIST, suite.stable_tests()):
        print test.path
    for test in filter(lambda test: test.name not in \
                       PRETEST_LIST, suite.stable_tests()):
        print test.path
    if options.add_experimental:
        for test in suite.unstable_tests():
            print test.path


if __name__ == "__main__":
    sys.exit(main())
