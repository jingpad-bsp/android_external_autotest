#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A utility program that generate an exclusive list of gesture file names."""


import getopt
import os
import re
import sys


def exclude_gesture_files(summary_file):
    """Generate an exclusive list of gesture file names.

    This function picks up the failed gesture files from the test summary file
    and appends them in the exclusive_list.
    """
    # A reported failed test in a summary file looks like:
    #   scroll-basic_two_finger.down-alex-bdc_tut1-20111213_220835.dat:
    FILE_PATT = '\s*(.+\.dat):'
    exclusive_list = []
    with open(summary_file) as f:
        for line in f:
            result = re.search(FILE_PATT, line, re.I)
            if result is not None:
                exclusive_list.append(result.group(1))
    return exclusive_list


def _usage():
    """Print the usage of this program."""
    print 'Usage: $ %s [options]\n' % sys.argv[0]
    print 'options:'
    print '  -s, --summary=<summary_file>'
    print '      <summary_file>: the summary file containing failed cases'
    print '  -e, --exclusive=<exclusive_file>'
    print '      <exclusive_file>: the resultant exclusive file list'
    print '  -h, --help: show this help'
    print


def _parsing_error(msg):
    """Print the usage and exit when encountering parsing error."""
    print 'Error: %s' % msg
    _usage()
    sys.exit(1)


def _parse_options():
    """Parse the command line options."""

    def _check_option(opt):
        """Check if the option has been specified."""
        if option_dict[opt] is None:
            msg = 'Error: please specify "--%s".' % opt
            _parsing_error(msg)

    try:
        short_opt = 'e:s:h'
        long_opt = ['summary', 'help']
        opts, args = getopt.getopt(sys.argv[1:], short_opt, long_opt)
    except getopt.GetoptError, err:
        _parsing_error(str(err))

    # Initialize the option dictionary
    option_dict = {}
    option_dict['summary'] = None
    option_dict['exclusive'] = None
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            _usage()
            sys.exit(1)
        elif opt in ('-s', '--summary'):
            if os.path.isfile(arg):
                option_dict['summary'] = arg
            else:
                print 'Error: the summary file "%s" does not exist.' % arg
                sys.exit(1)
        elif opt in ('-e', '--exclusive'):
            option_dict['exclusive'] = arg
        else:
            msg = 'Error: This option %s is not handled in program' % opt
            _parsing_error(msg)

    _check_option('summary')
    return option_dict


def main():
    """Run trackpad autotest on all gesture sets and create a summary report."""
    option_dict = _parse_options()
    if option_dict['exclusive'] is not None:
        exclusive_file_name = option_dict['exclusive']
    else:
        exclusive_file_name = 'exclusive_gesture_files'

    exclusive_list = exclude_gesture_files(option_dict['summary'])
    with open(exclusive_file_name, 'w') as f:
        for line in exclusive_list:
            f.write(line + '\n')


if __name__ == '__main__':
    main()
