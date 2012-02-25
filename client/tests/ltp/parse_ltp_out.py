#!/usr/bin/python
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Report summarizer of internal test pass% from running many tests in LTP.

LTP is the Linux Test Project from http://ltp.sourceforge.net/.

This script serves to summarize the results of a test run by LTP test
infrastructure.  LTP frequently runs >1000 tests so summarizing the results
by result-type and count is useful. This script is invoked by the ltp.py
wrapper in Autotest as a post-processing step to summarize the LTP run results
in the Autotest log file.

This script may be invoked by the command-line as follows:

$ ./parse_ltp_out.py -l /mypath/ltp.out
"""

import optparse
import os
import re
import sys


# Prefix char used in summaries:
# +: sums into 'passing'
# -: sums into 'notpassing'
TEST_FILTERS = {'TPASS': '+Pass', 'TFAIL': '-Fail', 'TBROK': '-Broken',
                'TCONF': '-Config error', 'TRETR': 'Retired',
                'TWARN': '+Warning'}


def parse_args(argv):
    """Setup command line parsing options.

    Args:
        argv: command-line arguments.

    Returns:
        parsed option result from optparse.
    """
    parser = optparse.OptionParser('Usage: %prog --ltp-out-file=/path/ltp.out')
    parser.add_option(
        '-l', '--ltp-out-file',
        help='[required] Path and file name for ltp.out [default: %default]',
        dest='ltpoutfile',
        default=None)
    options, args = parser.parse_args()
    if not options.ltpoutfile:
        parser.error('You must supply a value for --ltp-out-file.')

    return options


def _filter_and_count(ltpoutfile, test_filters):
    """Utility function to count lines that match certain filters.

    Args:
        ltpoutfile: human-readable output file from LTP -p (ltp.out).
        test_filters: dict of the tags to match and corresponding print tags.

    Returns:
        A dictionary with counts of the lines that matched each tag.
    """
    marker_line = '^<<<%s>>>$'
    status_line_re = re.compile('^\w+ +\d+ +(\w+) +: +\w+')
    filter_accumulator = dict.fromkeys(test_filters.keys(), 0)
    parse_states = (
        {'filters': {},
         'terminator': re.compile(marker_line % 'test_output')},
        {'filters': filter_accumulator,
         'terminator': re.compile(marker_line % 'execution_status')})

    # Simple 2-state state machine.
    state_test_active = False
    with open(ltpoutfile) as f:
        for line in f:
            state_index = int(state_test_active)
            if re.match(parse_states[state_index]['terminator'], line):
                # This state is terminated - proceed to next.
                state_test_active = not state_test_active
            else:
                # Determine if this line matches any of the sought tags.
                m = re.match(status_line_re, line)
                if m and m.group(1) in parse_states[state_index]['filters']:
                    parse_states[state_index]['filters'][m.group(1)] += 1
    return filter_accumulator


def _print_summary(filters, accumulator):
    """Utility function to print the summary of the parsing of ltp.out.

    Prints a count of each type of test result, then a %pass-rate score.

    Args:
        filters: map of tags sought and corresponding print headers.
        accumulator: counts of test results with same keys as filters.
    """
    border = 80 * '-'
    print border
    print 'Linux Test Project (LTP) Run Summary:'
    print border
    # Size the header to the largest printable tag.
    fmt = '%%%ss: %%s' % max(map(lambda x: len(x), filters.values()))
    for k in sorted(filters):
         print fmt % (filters[k], accumulator[k])

    print border
    # These calculations from ltprun-summary.sh script.
    pass_count = sum([accumulator[k] for k in filters if filters[k][0] == '+'])
    notpass_count = sum([accumulator[k] for k in filters
                                        if filters[k][0] == '-'])
    total_count = pass_count + notpass_count
    if total_count:
      score = float(pass_count) / float(total_count) * 100.0
    else:
      score = 0.0
    print 'SCORE.ltp: %.2f' % score
    print border


def summarize(ltpoutfile):
    """Scan detailed output from LTP run for summary test status reporting.

    Looks for all possible test result types know to LTP: pass, fail, broken,
    config error, retired and warning.  Prints a summary.

    Args:
        ltpoutfile: human-readable output file from LTP -p (ltp.out).
    """
    if not os.path.isfile(ltpoutfile):
        print 'Unable to locate %s.' % ltpoutfile
        return

    _print_summary(TEST_FILTERS, _filter_and_count(ltpoutfile, TEST_FILTERS))


def main(argv):
    """ Parse the human-readable logs from an LTP run and print a summary.

    Args:
        argv: command-line arguments.
    """
    options = parse_args(argv)
    summarize(options.ltpoutfile)


if __name__ == '__main__':
    main(sys.argv)
