#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

''' Guide users to record various gestures so that the gesture files can be
replayed later to test trackpad drivers.
'''

import getopt
import glob
import os
import re
import subprocess
import sys
import termios
import time
import tty
import types

import mini_color
import trackpad_util

from trackpad_util import read_trackpad_test_conf


def _getch():
    ''' Get a single character '''
    fin = sys.stdin
    old_attrs = termios.tcgetattr(fin)
    tty.setraw(fin.fileno())
    try:
        ch = fin.read(1)
    except ValueError:
        ch = ''
    finally:
        termios.tcsetattr(fin, termios.TCSADRAIN, old_attrs)
    return ch


def _check_program_existence(program):
    return os.system('which %s > /dev/null 2>&1' % program) == 0


def _system_output(command):
    ''' Execute a system command and return its output '''
    import tempfile
    tmp = tempfile.TemporaryFile()
    command_list = command.split()
    # Check if the program exits
    if _check_program_existence(command_list[0]):
        print 'Warning: "%s" does not exist in $PATH' % program
        subprocess.Popen(command_list, stdout=tmp).wait()
        tmp.seek(0)
        output = tmp.read()
        tmp.close()
        return output
    else:
        return None


class Record:
    ''' Record device events from the device event file '''

    def __init__(self, (trackpad_device_file, opt_func_list, tester,
                        flag_continue)):
        self.trackpad_device_file = trackpad_device_file
        self.opt_func_list = opt_func_list
        self.tester_name = tester
        self.flag_continue = flag_continue
        self.filename_attr = read_trackpad_test_conf('filename_attr', '.')
        self.system_model = trackpad_util.get_model()
        self.functionality_list = \
                           read_trackpad_test_conf('functionality_list', '.')
        self.func_dict = dict((func.name, func)
                              for func in self.functionality_list)
        self.display = trackpad_util.Display()
        self.display.calc_center()
        print 'Model name: %s' % self.system_model

    def _create_file_name(self, func, subname):
        ''' Create the file name based on filename_attr

        func: an object describing the functionality
          func.name: the functionality name of the gesture data file
          func.area: the area of this functionality

        subname: an individual subname of the functionality.
              It could look as simple as a tuple of strings
                    ('up', 'down'),
              or it could look more complicated as a tuple of tuples
                    (('physical', 'tap'), ('left', 'right'), ('0', '90', '180'))

        File name composition:
        (1) The file name must start with a functionality with optional subname.
        (2) And then there are a couple of optional attributes, e.g., model,
            firmware_version, etc. A user can create some other optional
            attributes too, e.g.,
                ['ODM': XXX],
                ['OEM': YYY],
                ['register_set': 'v3.5'],
        (3) The 'tester' name is required.
        (4) The file name ends with a timestamp before an optional file
            extension.
        (5) If the file extension is not necessary, just use the following line
            in filename_attr in the configuration file:
                ['ext': None],

        An example file name for two_finger_scroll with subname='down' and
            filename_attr = [
                ['model', 'alex'],
                ['firmware_version', None],
                ['ODM': XXX],
                ['tester', 'john'],
                ['ext', 'dat']
            ]
        in the configuration file looks as:
        two_finger_scroll.down-alex-XXX-john-20110407_185746.dat
        '''
        if subname is not None:
            if isinstance(subname, tuple):
                name_list = list(subname)
                name_list.insert(0, func.name)
            else:
                name_list = [func.name, subname]
            full_func_name = '.'.join(name_list)
        else:
            full_func_name = func.name

        file_name = full_func_name
        time_format = '%Y%m%d_%H%M%S'
        for attr in self.filename_attr:
            # Add prefix as appropriate
            if attr[0] == 'prefix':
                prefix = trackpad_util.get_prefix(func)
                if prefix is not None:
                    file_name = '-'.join([prefix, file_name])
                continue
            # Add timestamp just before file extension
            if attr[0] == 'ext':
                # Express the time in UTC
                file_name = '-'.join([file_name, time.strftime(time_format,
                                                               time.gmtime())])
            # Add the tester name
            if attr[0] == 'tester':
                attr[1] = self.tester_name
            # Add the model name
            if attr[0] == 'model' and attr[1] == 'DEFAULT':
                attr[1] = self.system_model
            # Now, add any other attribute
            if attr[1] is not None:
                sep = '.' if attr[0] == 'ext' else '-'
                file_name = sep.join([file_name, attr[1]])

        return (file_name, full_func_name)

    def _terminate(self):
        ''' Terminate the recording process '''
        self.rec_proc.terminate()
        self.rec_proc.wait()
        self.rec_f.close()

    def _record(self, func_name, subname, gesture_files_path, record_program):
        ''' Guide a user to record a gesture data file with proper prompts

        func_name: the functionality name of the gesture data file
        subname: the subname of the functionality
        gesture_files_path: the path to save gesture data files
        record_program: the device event recording program

        Return True for continuing, and False to break the loop in record_all()
        '''
        func = self.func_dict[func_name]
        prompt = func.prompt
        if isinstance(subname, tuple):
            subprompt = reduce(lambda s1, s2: s1 + s2,
                               tuple(func.subprompt[s] for s in subname))
        elif subname is None or func.subprompt is None:
            subprompt = None
        else:
            subprompt = func.subprompt[subname]

        if subprompt is None:
            color_prompt = prompt
        else:
            color_prompt = mini_color.string(prompt, '{', '}', 'green')
            color_prompt = color_prompt.format(*subprompt)

        func_msg = '  <%s>:\n%s%s'
        color_func_msg = mini_color.string(func_msg, '<', '>', 'blue')

        prefix_space = '        '
        prompt_choice = prefix_space + 'Enter your choice: '

        prompt_msg = '''
        Press 's' to save this file and record next gesture,
              'a' to save this file and record another file for this gesture.
              'd' to delete and record again,
              'q' to save this file and exit, or
              'x' to discard this file and exit.'''

        while True:
            self.display.move_cursor_to_center()
            (file_name, full_func_name) = self._create_file_name(func, subname)
            file_path = os.path.join(gesture_files_path, file_name)

            # Skip recording this file if this gesture exists already
            area_func = file_name.split(self.tester_name)[0]
            files = glob.glob(os.path.join(gesture_files_path, area_func) + '*')
            if files:
                print '  Skip recording existing "%s" gestures.' % area_func
                return True

            print color_func_msg % (full_func_name, prefix_space, color_prompt)
            self.rec_f = open(file_path, 'w')
            # -1 in the following record_cmd means that the recording program
            # does not terminate until it receives SIGINT or SIGTERM.
            record_cmd = '%s %s -1' % (record_program,
                                       self.trackpad_device_file)
            self.rec_proc = subprocess.Popen(record_cmd.split(),
                                             stdout=self.rec_f)
            print prompt_msg

            saved_msg = prefix_space + '(saved: %s)\n' % file_name
            deleted_msg = prefix_space + '(deleted: %s)\n' % file_name

            # Keep prompting the user until a valid choice is entered.
            while True:
                print prompt_choice,
                choice = _getch().lower()
                print choice
                if choice == 's':
                    print saved_msg
                    self._terminate()
                    return True
                elif choice == 'a':
                    print saved_msg
                    self._terminate()
                    break
                elif choice == 'd':
                    self._terminate()
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print deleted_msg
                    break
                elif choice == 'q':
                    print saved_msg
                    self._terminate()
                    return False
                elif choice == 'x':
                    self._terminate()
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print deleted_msg
                    return False
                else:
                    print prefix_space + 'Please press one of the above keys!'

    def record_all(self):
        ''' Record all gestures specified in self.opt_func_list '''

        def _span(seq1, seq2):
            ''' Span seq1 on seq2

                where seq can be a tuple of string, or a tuple of tuples
                E.g., seq1 = (('a', 'b'), 'c')
                      seq2 = ('1', ('2', '3'))
                      res = (('a', 'b', '1'), ('a', 'b', '2', '3'),
                             ('c', '1'), ('c', '2', '3'))
                E.g., seq1 = ('a', 'b')
                      seq2 = ('1', '2', '3')
                      res  = (('a', '1'), ('a', '2'), ('a', '3'),
                              ('b', '1'), ('b', '2'), ('b', '3'))
                E.g., seq1 = (('a', 'b'), ('c', 'd'))
                      seq2 = ('1', '2', '3')
                      res  = (('a', 'b', '1'), ('a', 'b', '2'), ('a', 'b', '3'),
                              ('c', 'd', '1'), ('c', 'd', '2'), ('c', 'd', '3'))
            '''
            to_list = lambda s: list(s) if isinstance(s, tuple) else [s]
            return tuple(tuple(to_list(s1) + to_list(s2)) for s1 in seq1
                                                          for s2 in seq2)

        # Set up a gesture set to store the gesture files
        gs = trackpad_util.setup_tester_gesture_set(self.tester_name,
                                                    self.flag_continue)

        # Check whether the record program exists
        record_program = trackpad_util.record_program
        if not _check_program_existence(record_program):
            print 'Warning: "%s" does not exist in $PATH' % record_program
            sys.exit(1)

        print 'Begin recording ...\n'

        # Iterate through every functionality to record gesture files.
        for func_name, subname in self.opt_func_list:
            if subname is None:
                continued = self._record(func_name, None, gs, record_program)
            else:
                # If subname is a sequence of sequence, it looks like
                # (('click', 'tap'), ('l0', 'l1', 'l2', 'r0', 'r1', 'r2')), or
                # (('click', 'tap'), ('left', 'right'), ('0', '1', '2'))
                # Otherwise, subname is a one-level sequence and looks like
                # ('up', 'down')
                span_subname = reduce(_span, subname) \
                               if isinstance(subname[0], tuple) else subname
                for sub in span_subname:
                    continued = self._record(func_name, sub, gs, record_program)
                    if not continued:
                        break
            if not continued:
                print '\n  You choose to exit %s' % sys.argv[0]
                break
        print '  Gesture files have been saved in %s \n' % gs


def _usage():
    ''' Print the usage of this program. '''
    example_device_file = '/dev/input/event6'
    example_func_list = 'any_finger_click.l3,r2,r0+no_cursor_wobble'
    example_tester = 'john'

    # Print the usage
    print 'Usage: $ sudo %s [options]\n' % sys.argv[0]
    print 'options:'
    print "  -c, --continue: continue recording gestures in the tester's" \
          " gesture set."
    print '  -d, --device=<device>'
    print '         <device>: /dev/input/eventN'
    print '         the device file for trackpad\n'
    print '  -f, --functionality=<func_list>'
    print '         <func_list>: functionality[.subname]'
    print '         use "+" to concatenate functionalities to be recorded'
    print '         without space\n'
    print '  -t, --tester=<tester_name>'
    print '         <tester_name>: the name of the tester\n'
    print '  -h, --help: show this help\n'

    # Print some examples
    print 'Examples:'
    print '    $ sudo %s # use default settings in %s' % \
               (sys.argv[0], trackpad_util.trackpad_test_conf)
    print '    $ sudo %s -c' % sys.argv[0]
    print '    $ sudo %s -d %s' % (sys.argv[0], example_device_file)
    print '    $ sudo %s -f %s' % (sys.argv[0], example_func_list)
    print '    $ sudo %s -t %s' % (sys.argv[0], example_tester)


def _parse_options():
    ''' Parse the command line options. '''
    try:
        short_opt = 'chd:f:t:'
        long_opt = ['continue', 'help', 'device=', 'functionality=', 'tester=']
        opts, args = getopt.getopt(sys.argv[1:], short_opt, long_opt)
    except getopt.GetoptError, err:
        print 'Error: %s' % str(err)
        _usage()
        sys.exit(1)

    trackpad_device_file = None
    func_list = None
    tester = None
    flag_continue = False
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            _usage()
            sys.exit()
        elif opt in ('-c', '--continue'):
            flag_continue = True
        elif opt in ('-d', '--device'):
            if os.path.exists(arg):
                trackpad_device_file = arg
            else:
                print 'Warning: %s does not exist.' % arg
        elif opt in ('-f', '--functionality'):
            func_list = arg
        elif opt in ('-t', '--tester'):
            tester = arg
        else:
            print 'Error: This option %s is not handled in program.' % opt
            print '       Need to fix the program to support it.'
            sys.exit(1)

    return (trackpad_device_file, func_list, tester, flag_continue)


def _verify_file_existence(filename):
    ''' Verify the existence of a file '''
    if filename is not None and not os.path.exists(filename):
        print 'Warning: %s does not exist.' % filename
        return None
    return filename


def _get_trackpad_device_file(trackpad_device_file):
    ''' Get and verify trackpad device file
        Priority 1: if there is a command line option of the device file
                    and the device file exists
        Priority 2: Get the device file from trackpad_util module
    '''
    # Verify the existence of the device file in the command line option
    trackpad_device_file = trackpad_util.file_exists(trackpad_device_file)

    if trackpad_device_file is not None:
        msg = 'The device file on command line: %s' % trackpad_device_file
    else:
        trackpad_device_file, msg = trackpad_util.get_trackpad_device_file()

    print msg
    if trackpad_device_file is None:
        sys.exit(1)
    return trackpad_device_file


def _get_functionality_list(func_list_str):
    ''' Get and verify functionality list

    Construct a functionality list based on its command line option.
    Verify the validity of the functionality list created from command line.
    If there is no command line option for functionality list, or if the
    functionality list on command line is not valid, use the functionality
    list in the configuration file instead.
    '''
    functionality_list = read_trackpad_test_conf('functionality_list', '.')
    if func_list_str is None:
        verified_opt_func_list = []
        for func in functionality_list:
            if func.enabled:
                verified_opt_func_list.append((func.name, func.subname))
    else:
        if '+' in func_list_str:
            opt_func_list = func_list_str.split('+')
        else:
            opt_func_list = [func_list_str]

        # Construct a functionality dictionary from trackpad_test.conf
        func_dict = dict((f.name, f.subname) for f in functionality_list)

        # Verify whether each of the command line functionalities exists in
        # functionality_list of trackpad_test.conf
        verified_opt_func_list = []
        for func_full_name in opt_func_list:
            if '.' in func_full_name:
                func_name, subname_str = func_full_name.split('.')
                subname = subname_str.split(',') if subname_str else None
            else:
                func_name = func_full_name
                subname = None
            # Check the validity of func_name
            if not func_dict.has_key(func_name):
                continue
            if subname is None:
                # When no specific subname is given, use whole subname.
                verified_subname = func_dict[func_name]
            else:
                # Check the validity of each subname
                sub_list = [s for s in subname if s in func_dict[func_name]]
                if not sub_list:
                    print 'No valid subname in %s' % func_name
                    print 'Please look up valid subname in %s' % \
                           trackpad_util.trackpad_test_conf
                    sys.exit()
                verified_subname = tuple(sub_list)
            verified_opt_func_list.append((func_name, verified_subname))

    return verified_opt_func_list


def _get_tester(tester):
    ''' Get tester name which is part of the gesture file name

        Priority 1: if there is a command line option specifying tester name
        Priority 2: if the tester in the configuration file is defined
        Priority 3: prompt the user to enter tester name
    '''
    if tester is None:
        # Read filename_attr from the configuration file
        filename_attr = read_trackpad_test_conf('filename_attr', '.')
        # If the tester name is not specified in the configuration file,
        # prompt the user to enter name here.
        name_msg = 'Please enter your name to be shown in a gesture file name: '
        for attr in filename_attr:
            if attr[0] == 'tester':
                tester = raw_input(name_msg) if attr[1] is None else attr[1]
                break
    return tester


def _get_options():
    ''' Get and verify all command line options

    Command line options supersede corresponding items specified in
    trackpad_test.conf
    '''
    # Parse command line options
    options = _parse_options()
    trackpad_device_file, func_list_str, tester, flag_continue = options

    # Verify the command line options. Check the configuration file if needed.
    trackpad_device_file = _get_trackpad_device_file(trackpad_device_file)
    verified_opt_func_list = _get_functionality_list(func_list_str)
    tester = _get_tester(tester)

    return (trackpad_device_file, verified_opt_func_list, tester, flag_continue)


if __name__ == '__main__':
    Record(_get_options()).record_all()
