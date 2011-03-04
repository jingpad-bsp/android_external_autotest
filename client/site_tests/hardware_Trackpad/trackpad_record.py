#!/usr/bin/python

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

''' Guide users to record various gestures so that the gesture files can be
replayed later to test trackpad drivers.
'''

import getopt
import os
import subprocess
import sys
import time
import trackpad_util

from trackpad_util import read_trackpad_test_conf


class Record:
    ''' Record device events from the device event file '''

    def __init__(self, (trackpad_device_file, opt_func_list, tester)):
        self.trackpad_device_file = trackpad_device_file
        self.opt_func_list = opt_func_list
        self.tester_name = tester
        self.filename_attr = read_trackpad_test_conf('filename_attr', '.')
        self.functionality_list = \
                read_trackpad_test_conf('functionality_list', '.')

    def _create_file_name(self, func_name, subname):
        ''' Create the file name based on filename_attr

        func_name: the functionality name of the gesture data file
        subname: the subname of the functionality

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

        An example file name for two_finger_scroll with subname=down and
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
        full_func_name = '.'.join([func_name, subname]) if subname \
                                                        else func_name
        file_name = full_func_name
        time_format = '%Y%m%d_%H%M%S'
        for attr in self.filename_attr:
            # Add timestamp just before file extension
            if attr[0] == 'ext':
                # Express the time in UTC
                file_name = '-'.join([file_name, time.strftime(time_format,
                                                               time.gmtime())])
            if attr[0] == 'tester':
                attr[1] = self.tester_name
            if attr[1] is not None:
                sep = '.' if attr[0] == 'ext' else '-'
                file_name = sep.join([file_name, attr[1]])
        return (file_name, full_func_name)

    def _terminate_record(self):
        self.rec_proc.terminate()
        self.rec_proc.wait()
        self.rec_f.close()

    def _record(self, func_name, subname, gesture_files_path, record_program):
        ''' Guide a user to record a gesture data file with proper prompts

        func_name: the functionality name of the gesture data file
        subname: the subname of the functionality
        gesture_files_path: the path to save gesture data files

        Return True for continuing, and False to break in record_all()
        '''
        for func in self.functionality_list:
            if func_name == func.name:
                prompt = func.prompt
                subprompt = func.subprompt[subname]
        full_prompt = prompt % subprompt

        func_msg = '  [%s]:\n%s%s'
        prefix_space = '        '
        timeout_msg = '(Recording terminates if not touching for 10 seconds.)'
        prompt_choice = prefix_space + 'Enter your choice: '

        prompt_msg = '''
        Press 's' to save this file and record next gesture,
              'r' to save this file and record another file for this gesture.
              'd' to delete and record again,
              'q' to save this file and exit, or
              'x' to discard this file and exit.'''

        while True:
            (file_name, full_func_name) = self._create_file_name(func_name,
                                                                 subname)
            file_path = os.path.join(gesture_files_path, file_name)
            print func_msg % (full_func_name, prefix_space, full_prompt)
            print prefix_space + timeout_msg
            self.rec_f = open(file_path, 'w')
            record_cmd = '%s %s' % (record_program, self.trackpad_device_file)
            self.rec_proc = subprocess.Popen(record_cmd.split(),
                                             stdout=self.rec_f)
            print prompt_msg

            saved_msg = prefix_space + '(saved: %s)\n' % file_name
            deleted_msg = prefix_space + '(deleted: %s)\n' % file_name

            # Keep prompting the user until a valid choice is entered.
            while True:
                choice = raw_input(prompt_choice).lower()
                if choice == 's':
                    print saved_msg
                    self._terminate_record()
                    return True
                elif choice == 'r':
                    print saved_msg
                    self._terminate_record()
                    break
                elif choice == 'd':
                    self._terminate_record()
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print deleted_msg
                    break
                elif choice == 'q':
                    print saved_msg
                    self._terminate_record()
                    return False
                elif choice == 'x':
                    self._terminate_record()
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print deleted_msg
                    return False
                else:
                    print prefix_space + 'Please press one of the above keys!'

    def record_all(self):
        ''' Record all gestures specified in self.opt_func_list '''

        # Get the gesture files path. Create the path if not existent.
        gesture_files_path = read_trackpad_test_conf('gesture_files_path', '.')
        if not os.path.exists(gesture_files_path):
            os.makedirs(gesture_files_path)
            print '  %s has been created successfully.' % gesture_files_path

        # Check whether the record program exists
        record_program = trackpad_util.record_program
        ret = os.system('which %s > /dev/null' % record_program)
        if ret != 0:
            print 'Error: The record program %s does not exist' \
                  ' in your $PATH.' % record_program
            sys.exit(1)

        print 'Gesture files will be stored in %s \n' % gesture_files_path
        print 'Note: The record program for each gesture file terminates'
        print '      if there is no finger on the trackpad for 10 seconds.\n'
        print 'Begin recording ...\n'

        # Iterate through every functionality to record gesture files.
        for func_name, subname in self.opt_func_list:
            if subname is None:
                continued = self._record(func_name, None, gesture_files_path,
                                         record_program)
            else:
                for sub in subname:
                    continued = self._record(func_name, sub, gesture_files_path,
                                             record_program)
                    if not continued:
                        break
            if not continued:
                print '\n  You choose to exit %s' % sys.argv[0]
                break
        print '  Gesture files are stored under %s \n' % gesture_files_path


def _usage():
    ''' Print the usage of this program. '''
    example_device_file = '/dev/input/event6'
    example_func_list = 'any_finger_click.l3,r2,r0+no_cursor_wobble'
    example_tester = 'john'

    # Print the usage
    print 'Usage: $ sudo %s [options]\n' % sys.argv[0]
    print 'options:'
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
    print '    $ sudo %s -d %s' % (sys.argv[0], example_device_file)
    print '    $ sudo %s -f %s' % (sys.argv[0], example_func_list)
    print '    $ sudo %s -t %s' % (sys.argv[0], example_tester)


def _parse_options():
    ''' Parse the command line options. '''
    try:
        short_opt = 'hd:f:t:'
        long_opt = ['help', 'device=', 'functionality=', 'tester=']
        opts, args = getopt.getopt(sys.argv[1:], short_opt, long_opt)
    except getopt.GetoptError, err:
        print 'Error: %s' % str(err)
        _usage()
        sys.exit(1)

    trackpad_device_file = None
    func_list = None
    tester = None
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            _usage()
            sys.exit()
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

    return (trackpad_device_file, func_list, tester)


def _verify_file_existence(filename):
    ''' Verify the existence of a file '''
    if filename is not None and not os.path.exists(filename):
        print 'Warning: %s does not exist.' % filename
        return None
    return filename


def _get_trackpad_device_file(trackpad_device_file):
    ''' Get and verify trackpad device file
        Priority 1: if there is a command line option specifying the device
                    file and the device file exists
        Priority 2: if trackpad_device_file in the configuration file is
                    defined and the file exists
        Priority 3: if the trackpad device file cannot be determined above,
                    using the hard coded one in trackpad_util

    '''
    # Determine trackpad device file
    # Verify the existence of the device file in the option
    trackpad_device_file = _verify_file_existence(trackpad_device_file)

    # Read and verify the existence of the configured device file
    config_dev = read_trackpad_test_conf('trackpad_device_file', '.')
    trackpad_device_file_configured = _verify_file_existence(config_dev)

    # Read and verify the existence of the hard coded device file
    hard_dev = trackpad_util.trackpad_device_file_hardcoded
    trackpad_device_file_hardcoded = _verify_file_existence(hard_dev)

    trackpad_test_conf = trackpad_util.trackpad_test_conf
    if trackpad_device_file is not None:
        msg = 'The device file %s on command line is used.'
        print msg % trackpad_device_file
    elif trackpad_device_file_configured is not None:
        trackpad_device_file = trackpad_device_file_configured
        msg = 'The device file %s in %s is used.'
        print msg % (trackpad_device_file_configured, trackpad_test_conf)
    elif trackpad_device_file_hardcoded is not None:
        trackpad_device_file = trackpad_device_file_hardcoded
        warn_msg1 = 'Warning: Please update the device file in %s \n'
        warn_msg2 = 'The default device %s hard coded in trackpad_util is used.'
        print warn_msg1 % trackpad_test_conf
        print warn_msg2 % trackpad_device_file_hardcoded
    else:
        err_msg = 'Error: the device file (%s) is not available'
        print err_msg % trackpad_device_file
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
                subname = None if subname_str == '' else subname_str.split(',')
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
                if len(sub_list) == 0:
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
                tester = raw_input(name_msg) if attr[1] is None \
                                                  else attr[1]
                break
    return tester


def _get_options():
    ''' Get and verify all command line options

    Command line options supersede corresponding items specified in
    trackpad_test.conf
    '''
    # Parse command line options
    trackpad_device_file, func_list_str, tester = _parse_options()

    # Verify the command line options. Check the configuration file if needed.
    trackpad_device_file = _get_trackpad_device_file(trackpad_device_file)
    verified_opt_func_list = _get_functionality_list(func_list_str)
    tester = _get_tester(tester)

    return (trackpad_device_file, verified_opt_func_list, tester)


if __name__ == '__main__':
    Record(_get_options()).record_all()
