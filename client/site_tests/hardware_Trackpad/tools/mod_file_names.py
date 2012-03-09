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


DIR = 'dir'
FILE = 'file'
PREFIX_SPACE = {DIR: ' ' * 2, FILE: ' ' * 4}


def mod_name(name, file_type, replacement, label):
    """Strip off the user name.

    The original file name looks like
        'scroll-basic_two_finger.down-alex-mary_tut1-20111215_000933.dat'
    If label is 'tut1' and replacement is 'user', the new file name looks like
        'scroll-basic_two_finger.down-alex-user_tut1-20111215_000933.dat'
    """
    # For example, assume that label is 'tut1' and replacement is 'user'
    # file: patt_str looks like '-mary_tut1-'
    #       replacement_str looks like '-user_tut1-'
    # directory: patt_str looks like 'mary_tut1-'
    #       replacement_str looks like 'user_tut1-'
    if file_type == FILE:
        patt_str = '-\w+_%s-' % label
        replacement_str = '-%s_%s-' % (replacement, label)
    elif file_type == DIR:
        patt_str = '/\w+_%s_' % label
        replacement_str = '/%s_%s_' % (replacement, label)
    else:
        return None

    new_name = re.sub(patt_str, replacement_str, name)
    if new_name != name:
        os.rename(name, new_name)
        space = PREFIX_SPACE[file_type]
        print '%sOld %s name: %s' % (space, file_type, name)
        print '  %s> New %s name: %s' % (space, file_type, new_name)

    return new_name


def mod_dir(dir_name, replacement, label):
    """Strip the user name off the files in the specified directory recursively.

    The original file name looks like
        'scroll-basic_two_finger.down-alex-mary_tut1-20111215_000933.dat'
    If label is 'tut1' and replacement is 'user', the new file name looks like
        'scroll-basic_two_finger.down-alex-user_tut1-20111215_000933.dat'
    """
    if not os.path.isdir(dir_name):
        print 'Error: the directory "%s" does not exist.' % dir_name
        return

    for f in glob.glob(os.path.join(dir_name, '*')):
        if os.path.isdir(f):
            new_dir_name = mod_name(f, DIR, replacement, label)
            mod_dir(new_dir_name, replacement, label)
        elif os.path.isfile(f):
            mod_name(f, FILE, replacement, label)


def _usage():
    """Print the usage of this program."""
    # Print the usage
    print 'Usage: $ %s [options]\n' % sys.argv[0]
    print 'options:'
    print '  -d, --dir=<gesture_directory>'
    print '            <gesture_directory>: containing gesture files'
    print '  -h, --help: show this help'
    print '  -l, --label: The user name must come with this label.'
    print '  -r, --replace=<replacement>:'
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

    try:
        short_opt = 'd:hl:r:'
        long_opt = ['dir', 'help', 'label', 'replace']
        opts, args = getopt.getopt(sys.argv[1:], short_opt, long_opt)
    except getopt.GetoptError, err:
        _parsing_error(str(err))

    # Initialize the option dictionary
    option_dict = {}
    option_dict['dir'] = '.'
    option_dict['label'] = None
    option_dict['replace'] = None
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            _usage()
            sys.exit(1)
        elif opt in ('-d', '--dir'):
            if os.path.isdir(arg):
                option_dict['dir'] = arg
            else:
                print 'Error: the directory "%s" does not exist.' % arg
                sys.exit(1)
        elif opt in ('-l', '--label'):
            option_dict['label'] = arg
        elif opt in ('-r', '--replace'):
            option_dict['replace'] = arg
        else:
            msg = 'Error: This option %s is not handled in program' % opt
            _parsing_error(msg)

    _check_option('label')
    _check_option('replace')

    return option_dict


def main():
    """Run trackpad autotest on all gesture sets and create a summary report."""
    # Parse command options
    option_dict = _parse_options()

    # Modify the file names recursively in the specified directory.
    mod_dir(option_dict['dir'], option_dict['replace'], option_dict['label'])


if __name__ == '__main__':
    main()
