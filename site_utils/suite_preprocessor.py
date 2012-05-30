#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool for preprocessing tests to determine their DEPENDENCIES.

Given an autotest root directory, this tool will aggregate the DEPENDENCIES of
all tests into a single file ready for later consumption by the dynamic suite
infrastructure.

Data will be written to stdout (or, optionally a file).  Format will be:

{'suite1': {'path/to/test1/control': set(['dep1', 'dep2']),
            'path/to/test2/control': set(['dep2', 'dep3'])},
 'suite2': {'path/to/test4/control': set(['dep6']),
            'path/to/test5/control': set(['dep7', 'dep3'])}}

This is intended for use only with Chrome OS test suits that leverage the
dynamic suite infrastructure in server/cros/dynamic_suite.py.
"""

import optparse, os, sys
import common
from autotest_lib.client.common_lib import control_data
from autotest_lib.server.cros import control_file_getter, dynamic_suite

def parse_options():
    parser = optparse.OptionParser()
    parser.add_option('-a', '--autotest_dir', dest='autotest_dir',
                      default=os.path.abspath(
                          os.path.join(os.path.dirname(__file__), '..')),
                      help="Directory under which to search for tests."\
                           " (e.g. /usr/local/autotest).  Defaults to '..'")
    parser.add_option('-o', '--output_file', dest='output_file',
                      default=None,
                      help='File into which to write collected test info.'\
                           '  Defaults to stdout.')
    options, _ = parser.parse_args()
    return options


def main():
    options = parse_options()

    fs_getter = dynamic_suite.Suite.create_fs_getter(options.autotest_dir)
    predicate = lambda t: hasattr(t, 'suite')  # Filter for tests in suites.
    test_deps = {}  #  Format will be {suite: {test: [dep, dep]}}.
    for test in dynamic_suite.Suite.find_and_parse_tests(fs_getter,
                                                         predicate,
                                                         True):
        if test.dependencies:
            for suite in dynamic_suite.Suite.parse_tag(test.suite):
                suite_deps = test_deps.setdefault(suite, {})
                suite_deps[test.path] = test.dependencies

    if options.output_file:
        with open(options.output_file, 'w+') as fd:
            fd.write('%r' % test_deps)
    else:
        print '%r' % test_deps

if __name__ == "__main__":
    sys.exit(main())
