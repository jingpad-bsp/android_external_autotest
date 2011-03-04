# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

''' Autotest program for verifying trackpad X level driver '''

import glob
import logging
import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from trackpad_util import read_trackpad_test_conf
from Xcapture import Xcapture
from Xcheck import Xcheck


class TrackpadData:
    ''' An empty class to hold global trackpad test data for communication
    between threads
    '''
    pass

''' tdata: trackpad data as a global variable used between threads
(1) The main thread runs in the hardware_Trackpad class will derive the test
    result through Xcheck class. The test result is stored in tdata.
    It requires read/write access to tdata.
(2) A second thread will launch a HTTP server that communicates with a
    chrome extension on the target machine to display the test result
    on the fly during the test procedure. When the result of a gesture file
    test has been derived, it is sent to the browser for display.

Note: it is not required to use mutex to protect the global tdata for two
    reasons:
    - tdata will be accessed sequentially between the two threads.
    - The main thread is a writer, and the HTTP server thread is a reader.
      No lock is needed in this case.
'''
tdata = TrackpadData()


class TrackpadDevice():
    ''' A trackpad device used to play back the device packets.
    The device file is usually '/dev/input/event*'.
    '''
    PLAYBACK_PROGRAM = 'evemu-play'

    def __init__(self, local_path):
        # Query which trackpad driver is used in xorg
        TOUCHPAD_CONF = ('/etc/X11/xorg.conf.d/touchpad.conf',
                         '/etc/X11/xorg.conf')
        TOUCHPAD_DRIVERS = ('synaptics', 'multitouch', 'cmt')
        conf_file_exist = False
        self.trackpad_driver = None
        for conf_file in TOUCHPAD_CONF:
            if os.path.exists(conf_file):
                conf_file_exist = True
                with open(conf_file) as f:
                    for line in f.read().splitlines():
                        if line.lstrip().startswith('Driver'):
                            driver = line.split()[1].strip('"')
                            if driver in TOUCHPAD_DRIVERS:
                                self.trackpad_driver = driver
                                break
                if self.trackpad_driver is not None:
                    break
        if not conf_file_exist:
            raise error.TestError('Xorg configuration files do not exist: %s' %
                                  str(TOUCHPAD_CONF))
        if self.trackpad_driver is None:
            raise error.TestError('Cannot find driver in %s.' %
                                  str(TOUCHPAD_CONF))
        logging.info('Trackpad driver "%s" is found.' % self.trackpad_driver)

        # Ungrab the device if the driver is synaptics and is grabbed
        self.grab_value = -1
        display_environ = 'DISPLAY=:0 XAUTHORITY=~chronos/.Xauthority '
        synclient_list_cmd = display_environ + 'synclient -l'
        self.grab_device = display_environ + 'synclient GrabEventDevice=%d'
        if self.trackpad_driver == 'synaptics':
            synclient_settings = utils.system_output(synclient_list_cmd)
            for line in synclient_settings.splitlines():
                if line.lstrip().startswith('GrabEventDevice'):
                    self.grab_value = int(line.split('=')[1].strip())
                    break
            logging.info('GrabEventDevice=%d.' % self.grab_value)
            if self.grab_value == -1:
                err_msg = 'Cannot find GrabEventDevice setting in "%s".'
                raise error.TestError(err_msg % synclient_list_cmd)
            # Ungrab the device only if it has been grabbed.
            elif self.grab_value == 1:
                try:
                    utils.system(self.grab_device % 0)
                except:
                    raise error.TestError('Fail to execute: %s' % ungrab_cmd)
                logging.info('The synaptics device file is ungrabbed now.')

        self.trackpad_device_file = read_trackpad_test_conf(
                                    'trackpad_device_file', local_path)

    def playback(self, packet_data_file):
        play_cmd = '%s %s < %s' % (TrackpadDevice.PLAYBACK_PROGRAM,
                                   self.trackpad_device_file, packet_data_file)
        utils.system(play_cmd)

    def __del__(self):
        # Grab the device again only if it was originally grabbed.
        if self.trackpad_driver == 'synaptics' and self.grab_value == 1:
            try:
                utils.system(self.grab_device % 1)
            except:
                raise error.TestError('Fail to execute: %s' % grab_cmd)
            logging.info('The synaptics device file is grabbed successfully.')


class hardware_Trackpad(test.test):
    ''' Play back device packets through the trackpad device. Capture the
    resultant X events. Analyze whether the X events meet the criteria
    of the functionality.
    '''
    version = 1

    def run_once(self):
        global tdata
        tdata.file_basename = None
        tdata.chrome_request = 0
        tdata.report_finished = False

        # Get functionality_list, and gesture_files_path from configuration file
        local_path = self.autodir + '/tests/hardware_Trackpad'
        functionality_list = read_trackpad_test_conf('functionality_list',
                                                     local_path)
        gesture_files_path_conf = read_trackpad_test_conf('gesture_files_path',
                                                          local_path)
        gesture_files_path = os.path.join(local_path, gesture_files_path_conf)
        logging.info('Path of trackpad gesture files: %s' % gesture_files_path)

        # Initialization of statistics
        tdata.num_wrong_file_name = 0
        tdata.num_files_tested = {}
        tdata.tot_fail_count = 0
        tdata.tot_num_files_tested = 0
        tdata.fail_count = dict([(tp_func.name, 0)
                                 for tp_func in functionality_list])
        logging.info('')
        logging.info('*** hardware_Trackpad autotest is started ***')

        # Start Trackpad Input Device
        self.tp_device = TrackpadDevice(local_path)

        # Start X events capture
        self.xcapture = Xcapture(error)

        # Initialize X events Check
        self.xcheck = Xcheck()

        # Processing every functionality in functionality_list
        # An example functionality is 'any_finger_click'
        for tdata.func in functionality_list:
            # If this function is not enabled in configuration file, skip it.
            if not tdata.func.enabled:
                continue;

            logging.info('\n')
            logging.info('Functionality: %s  (Area: %s)' %
                         (tdata.func.name, tdata.func.area))
            tdata.num_files_tested[tdata.func.name] = 0

            # Some cases of specifying gesture files in the configuration file:
            # Case 1:
            #   If gesture files are set to None in this functionality, skip it.
            #   It looks as:
            #       files=None,         or
            #       files=(None,),
            #
            # Case 2:
            #   '*' means all files starting with the functionality name
            #   Its setting in the configuration file looks as
            #       files='*',          or
            #       files=('*',),
            #
            # Case 3:
            # In other case, gesture files could be set as:
            #       ('any_finger_click.l1-*', 'any_finger_click.r*')
            if tdata.func.files is None or tdata.func.files.count(None) > 0:
                logging.info('    Gesture files is set to None. Skipped.')
                continue
            elif tdata.func.files == '*' or tdata.func.files.count('*') > 0:
                group_name_list = ('*',)
            else:
                group_name_list = tdata.func.files

            # A group name can be '*', or something looks like
            #                     'any_finger_click.l1-*', or
            #                     'any_finger_click.r*'), etc.
            for group_name in group_name_list:
                if group_name == '*':
                    group_name = tdata.func.name + '*'

                group_path = os.path.join(gesture_files_path, group_name)
                gesture_file_group = glob.glob(group_path)

                # Process each specific gesture_file now.
                for gesture_file in gesture_file_group:
                    # Every gesture file name should start with the correct
                    # functionality name, because we use the functionality to
                    # determine the test criteria for the file. Otherwise,
                    # a warning message is shown.
                    tdata.file_basename = os.path.basename(gesture_file)
                    if not tdata.file_basename.startswith(tdata.func.name):
                        warn_msg = 'The gesture file does not start with ' + \
                                   'correct functionality: %s'
                        logging.warning(warn_msg % gesture_file)
                        tdata.num_wrong_file_name += 1

                    gesture_file_path = os.path.join(gesture_files_path,
                                                     gesture_file)
                    logging.info('')
                    logging.info('    gesture file: %s' % tdata.file_basename)

                    # Start X events capture
                    self.xcapture.start(tdata.file_basename)

                    # Play back the gesture file
                    self.tp_device.playback(gesture_file_path)

                    # Wait until there are no more incoming X events.
                    self.xcapture.wait()

                    # Stop X events capture
                    self.xcapture.stop()

                    # Check X events
                    tdata.result = self.xcheck.run(tdata.func.name,
                                                   tdata.file_basename,
                                                   self.xcapture.read())

                    # Update statistics
                    tdata.num_files_tested[tdata.func.name] += 1
                    tdata.tot_num_files_tested += 1
                    if not tdata.result:
                        tdata.fail_count[tdata.func.name] += 1
                        tdata.tot_fail_count += 1

        # Logging test summary
        logging.info('\n')
        logging.info('*** Total number of failed / tested files: (%d / %d) ***'\
                     % (tdata.tot_fail_count, tdata.tot_num_files_tested))
        for tp_func in functionality_list:
            func = tp_func.name
            logging.info('    %s: (%d / %d) failed.' %
                  (func, tdata.fail_count[func], tdata.num_files_tested[func]))
        logging.info('\n')

        # Raise error.TestFail if there is any test failed.
        if tdata.tot_fail_count > 0:
            fail_str = 'Total number of failed files: %d' % tdata.tot_fail_count
            raise error.TestFail(fail_str)
