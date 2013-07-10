#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool for preprocessing tests to determine their DEPENDENCIES.

Given an autotest root directory, this tool will aggregate the DEPENDENCIES of
all tests into a single file ready for later consumption by the dynamic suite
infrastructure.  ALL DATA MUST BE STORED IN LITERAL TYPES!  Dicts, lists,
strings, etc.

Data will be written to stdout (or, optionally a file).  Format will be:

{'suite1': {'path/to/test1/control': set(['dep1', 'dep2']),
            'path/to/test2/control': set(['dep2', 'dep3'])},
 'suite2': {'path/to/test4/control': set(['dep6']),
            'path/to/test5/control': set(['dep7', 'dep3'])}}

This is intended for use only with Chrome OS test suites that leverage the
dynamic suite infrastructure in server/cros/dynamic_suite.py.
"""

import optparse, os, sys
import common
from autotest_lib.server.cros.dynamic_suite.suite import Suite


def parse_options():
    """Parse command line arguments."""
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


def get_all_suite_control_files(autotest_dir):
    """Find all control files in autotest_dir that have 'SUITE='

    @param autotest_dir: The directory to search for control files.
    @return: All control files in autotest_dir that have a suite attribute.
    """
    fs_getter = Suite.create_fs_getter(autotest_dir)
    predicate = lambda t: hasattr(t, 'suite')
    return Suite.find_and_parse_tests(fs_getter, predicate,
                                      add_experimental=True)


def calculate_dependencies(autotest_dir):
    """
    Traverse through the autotest directory and gather together the information
    as to what tests each suite contains and what the DEPENDENCIES of each test
    within a suite are.

    @param autotest_dir The path to the autotest directory to examine for tests
    @return A dictionary of the form {suite: {test: [dep, dep]}}.
    """
    test_deps = {}  #  Format will be {suite: {test: [dep, dep]}}.
    for test in get_all_suite_control_files(autotest_dir):
        for suite in Suite.parse_tag(test.suite):
            suite_deps = test_deps.setdefault(suite, {})
            # Force this to a list so that we can parse it later with
            # ast.literal_eval() -- which is MUCH safer than eval()
            if test.dependencies:
                suite_deps[test.path] = list(test.dependencies)
            else:
                suite_deps[test.path] = []
    return test_deps


def main():
    """Main function."""
    options = parse_options()

    test_deps = calculate_dependencies(options.autotest_dir)

    if options.output_file:
        with open(options.output_file, 'w') as file_obj:
            file_obj.write('%r' % test_deps)
    else:
        print '%r' % test_deps


if __name__ == "__main__":
    sys.exit(main())
