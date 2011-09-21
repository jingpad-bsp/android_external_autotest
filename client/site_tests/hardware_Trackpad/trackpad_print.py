#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

''' A utility module to print the gesture areas and functionalities '''


import getopt
import os
import sys

import trackpad_util

from trackpad_util import read_trackpad_test_conf


def _get_prompt(func, subname):
    prompt = func.prompt
    # Get subprompt
    if isinstance(subname, tuple):
        subprompt = reduce(lambda s1, s2: s1 + s2,
                           tuple(func.subprompt[s] for s in subname))
    elif subname is None:
        subprompt = None
    else:
        subprompt = func.subprompt[subname]

    # Get full prompt
    full_prompt = prompt if subprompt is None else prompt.format(*subprompt)

    # Get full_func_name
    if subname is not None:
        if isinstance(subname, tuple):
            name_list = list(subname)
            name_list.insert(0, func.name)
        else:
            name_list = [func.name, subname]
        full_func_name = '.'.join(name_list)
    else:
        full_func_name = func.name

    space_func = ' ' * 4
    space_prompt = ' ' * 8
    print '%s<%s>' % (space_func, full_func_name)
    print '%s%s\n' % (space_prompt, full_prompt)


def _span(seq1, seq2):
    to_list = lambda s: list(s) if isinstance(s, tuple) else [s]
    return tuple(tuple(to_list(s1) + to_list(s2)) for s1 in seq1
                                                  for s2 in seq2)


def print_gestures():
    ''' Print gesture areas and functionalities '''
    functionality_list = read_trackpad_test_conf('functionality_list', '.')
    area = None
    count = 0
    for func in functionality_list:
        if func.area != area:
            area = func.area
            print '\n\nArea: ', area[0]
            print '=================================='

        print '\nfunctionality: ', func.name
        print '----------------------------------'
        space_description = ' ' * 0
        print '%sdescription: %s\n' % (space_description, func.description)

        # Iterate through every functionality to record gesture files.
        func_name = func.name
        subname = func.subname
        if subname is None:
            prompt = _get_prompt(func, subname)
            count += 1
        else:
            span_subname = (reduce(_span, subname)
                            if isinstance(subname[0], tuple) else subname)
            for sub in span_subname:
                prompt = _get_prompt(func, sub)
                count += 1

    print '\nTotal %d gesture varations.' % count


def _usage():
    ''' Print the usage of this program. '''
    # Print the usage
    print 'Usage: $ %s [options]\n' % sys.argv[0]
    print 'options:'
    print '  -c, --config=<config_file>'
    print '         <config_file>: the config file'
    print '         When omitted, use the default config file %s.' % \
          trackpad_util.trackpad_test_conf
    print '  -h, --help: show this help\n'


def _parse_options():
    ''' Parse the command line options. '''
    try:
        short_opt = 'hc:'
        long_opt = ['help', 'config=']
        opts, args = getopt.getopt(sys.argv[1:], short_opt, long_opt)
    except getopt.GetoptError, err:
        print 'Error: %s' % str(err)
        _usage()
        sys.exit(1)

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            _usage()
            sys.exit()
        elif opt in ('-c', '--config'):
            if os.path.isfile(arg):
                trackpad_util.trackpad_test_conf = arg
            else:
                print 'Error: the config file "%s" does not exist.' % arg
                sys.exit(1)
        else:
            print 'Error: This option %s is not handled in program.' % opt
            _usage()
            sys.exit(1)

    print 'Use config file: %s' % trackpad_util.trackpad_test_conf


def main():
    _parse_options()
    print_gestures()


if __name__ == '__main__':
    main()
