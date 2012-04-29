#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A utility program that strips the user name off the file names."""


import getopt
import glob
import os
import re
import sys

from operator import and_


DIR = 'dir'
FILE = 'file'
PREFIX_SPACE = {DIR: ' ' * 2, FILE: ' ' * 4}

# Command line options
OPT_DIR = 'dir'
OPT_HELP = 'help'
OPT_LABEL = 'label'
OPT_NAME = 'name'
OPT_REPLACE = 'replace'


def mod_name(file_name, file_type, replacement, user_type, user_str):
    """Strip off the user name.

    Case 1: '--label' is specified on command line (user == 'label')
    The original file name looks like
        'scroll-basic_two_finger.down-alex-mary_tut1-20111215_000933.dat'
    If label is 'tut1' and replacement is 'user', the new file name looks like
        'scroll-basic_two_finger.down-alex-user_tut1-20111215_000933.dat'

    Case 2: '--name' is specified on command line (user == 'name')
    The original file name looks like
        'scroll-basic_two_finger.down-alex-mary-20111215_000933.dat'
    If name is 'mary' and replacement is 'user', the new file name looks like
        'scroll-basic_two_finger.down-alex-user-20111215_000933.dat'
    """
    # Case 1: user_type is 'label'
    #   For example, assume that label is 'tut1' and replacement is 'user'
    #   file: patt_str looks like '-mary_tut1-'
    #         replacement_str looks like '-user_tut1-'
    #   directory: patt_str looks like 'mary_tut1-'
    #         replacement_str looks like 'user_tut1-'
    #
    # Case 2: user_type is 'name'
    #   For example, assume that name is 'mary' and replacement is 'user'
    #   file: patt_str looks like '-mary-'
    #         replacement_str looks like '-user-'
    #   directory: patt_str looks like 'mary-'
    #         replacement_str looks like 'user-'
    if file_type == FILE:
        if user_type == 'label':
            patt_str = '-\w+_%s-' % user_str
            replacement_str = '-%s_%s-' % (replacement, user_str)
        else:
            patt_str = '-%s-' % user_str
            replacement_str = '-%s-' % replacement
    elif file_type == DIR:
        if user_type == 'label':
            patt_str = '/\w+_%s_' % user_str
            replacement_str = '/%s_%s_' % (replacement, user_str)
        else:
            patt_str = '%s_' % user_str
            replacement_str = '%s_' % replacement
    else:
        return None

    new_file_name = re.sub(patt_str, replacement_str, file_name)
    if new_file_name != file_name:
        os.rename(file_name, new_file_name)
        space = PREFIX_SPACE[file_type]
        print '%sOld %s name: %s' % (space, file_type, file_name)
        print '  %s> New %s name: %s' % (space, file_type, new_file_name)

    return new_file_name


def mod_dir(dir_name, replacement, option_dict, user_type):
    """Strip the user name off the files in the specified directory recursively.

    Case 1: '--label' is specified on command line (user_type == 'label')
    The original dir name looks like
        mary_tut1_20120426_071316
    If label is 'tut1' and replacement is 'user', the new dir name looks like
        user_tut1_20120426_071316

    Case 2: '--name' is specified on command line (user_type == 'name')
    The original dir name looks like
        mary_20120426_071316
    If name is 'mary' and replacement is 'user', the new dir name looks like
        user_20120426_071316
    """
    if not os.path.isdir(dir_name):
        print 'Error: the directory "%s" does not exist.' % dir_name
        return

    # if user_type == 'label':
    #   The dir_name will be something like
    #       '/var/tmp/trackpad_test_data/test_files'
    #   under which there may exist a number of user sub-directories like
    #       'mary_tut1_20120426_071316'
    #       'jane_tut1_20120426_081526'
    # if user_type == 'name':
    #   The dir_name will be something like
    #       '/var/tmp/trackpad_test_data/test_files/mary_20120426_071316'
    new_dir_name = mod_name(dir_name, DIR, replacement, user_type,
                            option_dict[user_type])
    for f in glob.glob(os.path.join(new_dir_name, '*')):
        if os.path.isdir(f):
            new_dir_name = mod_name(f, DIR, replacement, user_type,
                                    option_dict[user_type])
            mod_dir(new_dir_name, replacement, option_dict, user_type)
        elif os.path.isfile(f):
            mod_name(f, FILE, replacement, user_type, option_dict[user_type])


def _usage():
    """Print the usage of this program."""
    # Print the usage
    print 'Usage: $ %s [options]\n' % sys.argv[0]
    print 'options:'
    print '  -d, --%s=<gesture_directory>' % OPT_DIR
    print '            <gesture_directory>: containing gesture files'
    print '  -h, --%s: show this help' % OPT_HELP
    print '  -l, --%s: The user name must come with this label.' % OPT_LABEL
    print '  -n, --%s: The user name to be replaced.' % OPT_NAME
    print '  -r, --%s=<replacement>:' % OPT_REPLACE
    print '                <replacement>: replace user name with this string'
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

    def _check_options(opt_list):
        """Check if exactly one option in the opt_list has been specified."""
        if (reduce(and_, [option_dict[opt] is None for opt in opt_list]) or
            reduce(and_, [option_dict[opt] is not None for opt in opt_list])):
            msg = 'Error: please specify exact one of %s.' % ' or '.join(
                  ['"--%s"' % opt for opt in opt_list])
            _parsing_error(msg)

    try:
        short_opt = 'd:hl:n:r:'
        long_opt = [OPT_DIR, OPT_HELP, OPT_LABEL, OPT_NAME, OPT_REPLACE]
        opts, args = getopt.getopt(sys.argv[1:], short_opt, long_opt)
    except getopt.GetoptError, err:
        _parsing_error(str(err))

    # Initialize the option dictionary
    option_dict = {}
    option_dict[OPT_DIR] = '.'
    option_dict[OPT_LABEL] = None
    option_dict[OPT_NAME] = None
    option_dict[OPT_REPLACE] = None
    for opt, arg in opts:
        if opt in ('-h', '--%s' % OPT_HELP):
            _usage()
            sys.exit(1)
        elif opt in ('-d', '--%s' % OPT_DIR):
            if os.path.isdir(arg):
                option_dict[OPT_DIR] = arg
            else:
                print 'Error: the directory "%s" does not exist.' % arg
                sys.exit(1)
        elif opt in ('-l', '--%s' % OPT_LABEL):
            option_dict[OPT_LABEL] = arg
        elif opt in ('-n', '--%s' % OPT_NAME):
            option_dict[OPT_NAME] = arg
        elif opt in ('-r', '--%s' % OPT_REPLACE):
            option_dict[OPT_REPLACE] = arg
        else:
            msg = 'Error: This option %s is not handled in program' % opt
            _parsing_error(msg)

    _check_options([OPT_LABEL, OPT_NAME])
    _check_option(OPT_REPLACE)

    return option_dict


def main():
    """Run trackpad autotest on all gesture sets and create a summary report."""
    # Parse command options
    option_dict = _parse_options()

    # Must specify either 'label' or 'name' to replace
    user_type = OPT_LABEL if option_dict[OPT_LABEL] is not None else OPT_NAME

    # Modify the file names recursively in the specified directory.
    mod_dir(option_dict[OPT_DIR], option_dict[OPT_REPLACE], option_dict,
            user_type)


if __name__ == '__main__':
    main()
