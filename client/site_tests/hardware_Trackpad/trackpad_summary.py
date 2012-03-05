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

import common_util

from trackpad_util import read_trackpad_test_conf, KEY_LOG, KEY_SEQ


# Define some constants and formats for parsing the result file
RESULT_END = 'End of Test Summary'
RESULT_STOP = 'stop'
RESULT_NOT_FUNCTIONALITY = 'not functionality'
RESULT_FORMAT_PASS_RATE = '      {0:<50}: {1:4s}  {2:9s} passed'
RESULT_PATTERN_PASS_RATE = \
        u'\s*(\S+)\s*:\s*\d+%\s*\s\(\s*(\d+)\D+(\d+)\s*\)\s*passed'
SUMMARY_LABEL = '_tut1_'
LINE_SPLIT = '\n'


def format_result_header(file_name, tot_pass_count, tot_count):
    """Format the result header."""
    header = []
    header.append(LINE_SPLIT)
    header.append('Result summary file: %s' % file_name)
    ratio = 0 if tot_count == 0 else (1.0 * tot_pass_count / tot_count)
    tot_pass_rate_str = '%3.0f%%' % (100.0 * ratio)
    header.append('*** Total pass rate: %s' % tot_pass_rate_str)
    msg = ('*** Total number of (passed / tested) files: (%d / %d)\n\n' %
           (tot_pass_count, tot_count))
    header.append(msg)
    return LINE_SPLIT.join(header)


def format_result_area(area_name):
    """Format of the area name."""
    return '  Area: %s' % area_name


def format_result_pass_rate(name, pass_count, test_count):
    """Format the line of the pass rate and pass count."""
    pass_rate_str = '%3.0f%%' % (100.0 * pass_count / test_count)
    count_str = '(%2d / %2d)' % (pass_count, test_count)
    return RESULT_FORMAT_PASS_RATE.format(name, pass_rate_str, count_str)


def format_result_body(summary_list, pass_count, tot_count, gss_vlog_dict,
                       flag_vlog=False):
    """Format the body of the test result."""
    body = []
    area = None
    for s in summary_list:
        if s.lstrip().startswith('Area'):
            body.append(s)
            # Extract area name
            #   e.g., "Area: click"
            area = s.split(':')[1].strip()
        else:
            if pass_count.has_key(s) and tot_count.has_key(s):
                line = format_result_pass_rate(s, pass_count[s], tot_count[s])
            else:
                line = '%s: %s' % (s, 'Warning: missing counts')
            if flag_vlog:
                line = LINE_SPLIT + line
            body.append(line)

            if flag_vlog:
                if area is not None:
                    # E.g.,
                    # area: click
                    # s: no_cursor_wobble.tap
                    # fullname: click-no_cursor_wobble.tap
                    fullname = '-'.join([area, s])
                    for filename, root_cause in \
                            gss_vlog_dict[KEY_LOG][fullname]:
                        line = '          %s:' % os.path.basename(filename)
                        body.append(line)
                        for c in root_cause:
                            rc = root_cause[c]
                            if isinstance(rc, list):
                                indent = '                  %s'
                                indent_rc = list(indent % str(i) for i in rc)
                                rc = LINE_SPLIT.join(indent_rc)
                                line = '              %s:\n%s' % (c, rc)
                            else:
                                line = '              %s: %s' % (c, rc)
                            body.append(line)

    return LINE_SPLIT.join(body)


def format_result_tail():
    """Format the tail of the result."""
    return '\n\n*** %s\n\n' % RESULT_END


def get_count_from_result_line(line):
    """Get the pass count and total count from a given line."""
    if RESULT_END in line:
        return RESULT_STOP

    # Try to extract information from a result line which looks as
    # '      no_cursor_wobble.tap             :   50%  ( 1 / 2 )  passed'
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


class TrackpadResult:
    ''' Calculate integrated results over a number of gesture sets '''

    def __init__(self, results_dir=None):
        if results_dir is None:
            result_name = 'gesture_files_path_results'
            results_dir = read_trackpad_test_conf(result_name, '.')

        self.results_dir = results_dir
        if not os.path.isdir(self.results_dir):
            os.makedirs(self.results_dir)
            print '"%s" is created.\n' % self.results_dir

        self._open_summary_file()
        print 'The summary file is saved in %s.\n' % self.summary_name

        msg = ('A report of trackpad autotest analysis on trackpad '
               'usability study\n')
        self.summary_file.write(msg)
        msg = '     Gesture Sets Results Directory: "%s"\n' % self.results_dir
        self.summary_file.write(msg)

        # Collect results_files from results_dir
        self.label = SUMMARY_LABEL
        _results = glob.glob(os.path.join(self.results_dir, '*'))
        self.results_files = filter(lambda f: self.label in f and
                                              os.path.isfile(f), _results)

    def _open_summary_file(self):
        time_format = '%Y%m%d_%H%M%S'
        summary_time = 'summary:' + time.strftime(time_format, time.gmtime())
        self.summary_name = os.path.join(self.results_dir, summary_time)
        self.summary_file = open(self.summary_name, 'w')

    def calc_test_summary(self, gss_vlog_dict, flag_vlog=False):
        """Calculate the test summary of test result files in the result_dir."""
        # Initialization
        pass_count = {}
        tot_count = {}
        fullname_list = []
        summary_list = []

        if not self.results_files:
            print 'Warning: no result files in "%s".' % self.results_dir
            return False

        if flag_vlog:
            msg = '\n\n\nThe detailed root causes of failed cases:\n'
            self.summary_file.write(msg)
            self.summary_file.write('-' *  len(msg.strip('\n')))

        for rfile in self.results_files:
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
                            if flag_vlog:
                                area_line = '\n' + area_line
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
                                msg = '  Warning: cannot insert %s into area %s'
                                print (msg % (fullname, area))

        # Calculate the final statistics
        if pass_count.values():
            final_pass_count = reduce(operator.add, pass_count.values())
        else:
            final_pass_count = 0
        if tot_count.values():
            final_tot_count = reduce(operator.add, tot_count.values())
        else:
            final_tot_count = 0

        # Create a test result summary
        header = format_result_header(self.summary_name, final_pass_count,
                                      final_tot_count)
        body = format_result_body(summary_list, pass_count, tot_count,
                                  gss_vlog_dict, flag_vlog=flag_vlog)
        tail = format_result_tail()

        self.summary_file.write(header)
        self.summary_file.write(body)
        self.summary_file.write(tail)

        return True

    def get_vlog(self, vlog_file):
        ''' Extract verification log from the vlog_file

        The files contains something like
            vlog{attr}={'log': {...}, 'seq': {...}}
        '''
        vlog_dict = None
        with open(vlog_file) as f:
            for line in f:
                if line.startswith('Verification Log'):
                    vlog_dict = eval(line.split('=', 1)[1])
                    break
        return vlog_dict

    def _result_exists(self, gesture_set):
        ''' Check if a result file of a gesture set (gs) already exists'''
        gs = os.path.basename(gesture_set)
        gs_in_results = filter(lambda result_file: gs in result_file,
                               self.results_files)
        return len(gs_in_results) > 0

    def hardware_trackpad_test_all(self, gss_path=None, allow_duplicate=False):
        ''' Run all trackpad autotest analysis on all gesture sets (gss)

        When allow_duplicate is True, it means to run autotest analysis for
        the gesture sets no matter whether the result files of the gesture
        sets exist or not.
        '''
        if gss_path is None:
            gss_path = read_trackpad_test_conf('gesture_files_path_root', '.')

        if not os.path.isdir(gss_path):
            print 'Error: "%s" does not exist.' % gss_path
            sys.exit(1)
        print '     Gesture Sets: "%s"' % gss_path

        autotest_link = read_trackpad_test_conf('gesture_files_path_autotest',
                                                '.')
        autotest_program = read_trackpad_test_conf('autotest_program', '.')

        for gs in glob.glob(os.path.join(gss_path, '*')):
            if (self.label in gs and
                (allow_duplicate or not self._result_exists(gs))):
                if os.path.islink(gs):
                    continue
                if os.path.isfile(gs):
                    continue
                print '  Test the gesture set "%s"' % gs
                if os.path.islink(autotest_link):
                    os.remove(autotest_link)
                os.symlink(gs, autotest_link)
                cmd = '%s %s' % (autotest_program, 'control')
                common_util.simple_system(cmd)

    def hardware_trackpad_vlog_all(self, results_dir=None, flag_vlog=False):
        ''' Collect all verification logs from all gesture set results path. '''

        if results_dir is None:
            results_dir = self.results_dir

        # Initialize a cross-iteration verification dictionary for all gss
        gss_vlog_dict = {}
        gss_vlog_dict[KEY_LOG] = {}
        gss_vlog_dict[KEY_SEQ] = []

        # Integrate all the verification log
        msg = '\nThis summary report is derived from the following %d users:\n'
        self.summary_file.write(msg % len(self.results_files))
        for result_file in self.results_files:
            vlog_dict = self.get_vlog(result_file)

            user_date = os.path.basename(result_file).split('.')[0]
            if SUMMARY_LABEL in user_date:
                user, date = user_date.split(SUMMARY_LABEL)
                msg = '     user: %s (%s)\n' % (user, date)
                self.summary_file.write(msg)

            if vlog_dict is not None:
                for gname in vlog_dict[KEY_SEQ]:
                    if gname not in gss_vlog_dict[KEY_SEQ]:
                        gss_vlog_dict[KEY_SEQ].append(gname)
                        gss_vlog_dict[KEY_LOG][gname] = []
                    if gname in vlog_dict[KEY_LOG]:
                        filename = vlog_dict[KEY_LOG][gname]['file']
                        root_cause = vlog_dict[KEY_LOG][gname]['root_cause']
                        gss_vlog_dict[KEY_LOG][gname].append([filename,
                                                            root_cause])

        # Print all the verification log
        if flag_vlog:
            print '\n\ngss_vlog_dict:'
            for gname in gss_vlog_dict[KEY_SEQ]:
                print '  %s:' % gname
                for filename, root_cause in gss_vlog_dict[KEY_LOG][gname]:
                    print '    %s:' % os.path.basename(filename)
                    for c in root_cause:
                        print '        %s: %s' % (c, root_cause[c])

        return gss_vlog_dict


def _usage():
    """Print the usage of this program."""
    # Print the usage
    print 'Usage: $ %s [options]\n' % sys.argv[0]
    print 'options:'
    print '  -d, --dir=<result_directory>'
    print '         <result_directory>: the path containing result files'
    print '  -e, --enforce: enforce to run autotest analysis. Default is False.'
    print '  -h, --help: show this help\n'


def _parsing_error(msg):
    """Print the usage and exit when encountering parsing error."""
    print 'Error: %s' % msg
    _usage()
    sys.exit(1)


def _parse_options():
    """Parse the command line options."""
    try:
        short_opt = 'hd:e'
        long_opt = ['help', 'dir=', 'enforce']
        opts, args = getopt.getopt(sys.argv[1:], short_opt, long_opt)
    except getopt.GetoptError, err:
        _parsing_error(str(err))

    # Initialize the option dictionary
    option_dict = {}
    option_dict['results_dir'] = read_trackpad_test_conf(
                                        'gesture_files_path_results', '.')
    option_dict['enforce'] = False
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            _usage()
            sys.exit(1)
        elif opt in ('-d', '--dir'):
            if os.path.isdir(arg):
                option_dict['results_dir'] = arg
            else:
                print 'Error: the result directory "%s" does not exist.' % arg
                sys.exit(1)
        elif opt in ('-e', '--enforce'):
            option_dict['enforce'] = True
        else:
            msg = 'Error: This option %s is not handled in program' % opt
            _parsing_error(msg)

    return option_dict


def main():
    """Run trackpad autotest on all gesture sets and create a summary report."""
    # Parse command options
    option_dict = _parse_options()
    tresult = TrackpadResult(results_dir=option_dict['results_dir'])

    # Determine whether to execute autotest analysis on gesture sets
    if option_dict['enforce']:
        tresult.hardware_trackpad_test_all()

    # Collect verification logs from all analysis logs
    gss_vlog_dict = tresult.hardware_trackpad_vlog_all()

    # Calculate the test summary over the analysis log without detailed logs
    tresult.calc_test_summary(gss_vlog_dict, flag_vlog=False)

    # List the test summary over the analysis log with detailed root causes
    # of failed cases
    tresult.calc_test_summary(gss_vlog_dict, flag_vlog=True)


if __name__ == '__main__':
    main()
