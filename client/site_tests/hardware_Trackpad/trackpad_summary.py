#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module calculates the test summary of specified test result files."""


import getopt
import glob
import operator
import os
import re
import sys
import time

import trackpad_util

from trackpad_util import read_trackpad_test_conf


# Define some constants and formats for parsing the result file
RESULT_END = 'End of Test Summary'
RESULT_STOP = 'stop'
RESULT_NOT_FUNCTIONALITY = 'not functionality'
RESULT_FORMAT_PASS_RATE = '      {0:<50}: {1:4s}  {2:9s} passed'
RESULT_PATTERN_PASS_RATE = u'\s*(\S+)\s*:\s*\d+%\s*\s\((\d+)\D+(\d+)\)\s*passed'
LINE_SPLIT = '\n'


def format_result_header(file_name, tot_pass_count, tot_count):
    """Format the result header."""
    header = []
    header.append(LINE_SPLIT)
    header.append('*** Result: %s ***' % file_name)
    tot_pass_rate_str = '%3.0f%%' % (100.0 * tot_pass_count / tot_count)
    header.append('*** Total pass rate: %s ***' % tot_pass_rate_str)
    msg = ('*** Total number of (passed / tested) files: (%d / %d) ***\n\n' %
           (tot_pass_count, tot_count))
    header.append(msg)
    return LINE_SPLIT.join(header)


def format_result_area(area_name):
    """Format of the area name."""
    return '  Area: %s' % area_name


def format_result_pass_rate(name, pass_count, test_count):
    """Format the line of the pass rate and pass count."""
    pass_rate_str = '%3.0f%%' % (100.0 * pass_count / test_count)
    count_str = '(%d / %d)' % (pass_count, test_count)
    return RESULT_FORMAT_PASS_RATE.format(name, pass_rate_str, count_str)


def format_result_body(summary_list, pass_count, tot_count):
    """Format the body of the test result."""
    body = []
    for s in summary_list:
        if s.lstrip().startswith('Area'):
            body.append(s)
        else:
            if pass_count.has_key(s) and tot_count.has_key(s):
                line = format_result_pass_rate(s, pass_count[s], tot_count[s])
            else:
                line = '%s: %s' % (s, 'Warning: missing counts')
            body.append(line)
    return LINE_SPLIT.join(body)


def format_result_tail():
    """Format the tail of the result."""
    return '\n\n### %s ###\n\n' % RESULT_END


def get_count_from_result_line(line):
    """Get the pass count and total count from a given line."""
    if RESULT_END in line:
        return RESULT_STOP

    # Try to extract information from a result line which looks as
    # '      no_cursor_wobble.tap             :   50%  (1 / 2)  passed.'
    m = re.search(RESULT_PATTERN_PASS_RATE, line)
    if m is None:
        return RESULT_NOT_FUNCTIONALITY

    fullname = m.group(1)
    single_pass_count = int(m.group(2))
    single_tot_count = int(m.group(3))
    return (fullname, single_pass_count, single_tot_count)


def insert_list(summary_list, fullname, area):
    """Insert a functionality fullname to the end of a given area."""
    if area is not None:
        summary_list_length = len(summary_list)
        if summary_list_length == 0:
            return False

        found_the_area = False
        index = None
        for i, s in enumerate(summary_list):
            if found_the_area:
                flag_found_next_area = re.search('Area:', s, re.I) is not None
                if flag_found_next_area:
                    index = i
                    break
            elif re.search('Area\s*:\s*%s' % area, s, re.I) is not None:
                found_the_area = True

        flag_end_of_list = (i == summary_list_length - 1)
        if index is None and found_the_area and flag_end_of_list:
            index = summary_list_length

        if index is not None:
            summary_list.insert(index, fullname)
            return True

    return False


def calc_test_summary(result_dir):
    """Calculate the test summary of test result files in the result_dir."""
    # Initialization
    pass_count = {}
    tot_count = {}
    summary_list = []

    if not os.path.isdir(result_dir):
        print 'Warning: "%s" does not exist.' % result_dir
        return False

    # To collect pass_count and tot_count from all result files
    result_files = glob.glob(os.path.join(result_dir, '*'))

    if len(result_files) == 0:
        print 'Warning: no result files in "%s".' % result_dir
        return False

    for rfile in result_files:
        with open(rfile) as f:
            area = None
            for line in f:
                rv = get_count_from_result_line(line)
                if rv == RESULT_NOT_FUNCTIONALITY:
                    # An area looks as
                    # '  Area: click '
                    m = re.search('\s*Area:\s*(\S+)\s*', line, re.I)
                    if m is not None:
                        area = m.group(1)
                        area_line = format_result_area(area)
                        if area_line not in summary_list:
                            summary_list.append(area_line)
                    continue
                elif rv == RESULT_STOP:
                    break
                else:
                    fullname, single_pass_count, single_tot_count = rv
                    if fullname not in pass_count:
                        pass_count[fullname] = 0
                        tot_count[fullname] = 0
                    pass_count[fullname] += single_pass_count
                    tot_count[fullname] += single_tot_count
                    if fullname not in summary_list:
                        # Insert the functionality fullname in the area
                        if not insert_list(summary_list, fullname, area):
                            print ('  Warning: cannot insert %s into area %s' %
                                   (fullname, area))

    # Calculate the final statistics
    final_pass_count = reduce(operator.add, pass_count.values())
    final_tot_count = reduce(operator.add, tot_count.values())

    # Create a test result summary
    time_format = '%Y%m%d_%H%M%S'
    summary_time = 'summary:' + time.strftime(time_format, time.gmtime())
    summary_name = os.path.join(result_dir, summary_time)
    header = format_result_header(summary_name, final_pass_count,
                                  final_tot_count)
    body = format_result_body(summary_list, pass_count, tot_count)
    tail = format_result_tail()

    print header
    print body
    print tail
    return True


def _usage():
    """Print the usage of this program."""
    # Print the usage
    print 'Usage: $ %s [options]\n' % sys.argv[0]
    print 'options:'
    print '  -d, --dir=<result_directory>'
    print '         <result_directory>: the path containing result files'
    print '  -h, --help: show this help\n'


def _parsing_error(msg):
    """Print the usage and exit when encountering parsing error."""
    print 'Error: %s' % msg
    _usage()
    sys.exit(1)


def _parse_options():
    """Parse the command line options."""
    try:
        short_opt = 'hd:'
        long_opt = ['help', 'dir=']
        opts, args = getopt.getopt(sys.argv[1:], short_opt, long_opt)
    except getopt.GetoptError, err:
        _parsing_error(str(err))

    result_dir = None
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            _usage()
            sys.exit(1)
        elif opt in ('-d', '--dir'):
            if os.path.isdir(arg):
                result_dir = arg
            else:
                print 'Error: the result directory "%s" does not exist.' % arg
                sys.exit(1)
        else:
            msg = 'Error: This option %s is not handled in program' % opt
            _parsing_error(msg)

    if result_dir is None:
        result_dir = read_trackpad_test_conf('gesture_files_path_results', '.')
    print 'result_dir: ', result_dir

    return result_dir


def main():
    """Run trackpad autotest on all gesture sets and create a summary report."""
    result_dir = _parse_options()
    trackpad_util.hardware_trackpad_test_all()
    calc_test_summary(result_dir)


if __name__ == '__main__':
    main()
