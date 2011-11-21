# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

''' Autotest program for verifying trackpad X level driver '''

import glob
import logging
import os
import time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui

from trackpad_device import TrackpadDevice
from trackpad_util import read_trackpad_test_conf, get_prefix
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


class hardware_Trackpad(test.test):
    ''' Play back device packets through the trackpad device. Capture the
    resultant X events. Analyze whether the X events meet the criteria
    of the functionality.
    '''
    version = 1

    def read_gesture_files_path(self, local_path, name):
        pathname = read_trackpad_test_conf(name, local_path)
        logging.info('Path of %s: %s' % (name, pathname))
        return pathname

    def _open_result_log(self, result_path, autotest_path):
        time_format = '%Y%m%d_%H%M%S'
        test_time = 'tested:' + time.strftime(time_format, time.gmtime())
        autotest_dir = os.path.realpath(autotest_path).split('/')[-1]
        result_file_name = '.'.join([autotest_dir, test_time])
        self.result_file = os.path.join(result_path, result_file_name)
        self.result_fh = open(self.result_file, 'w+')
        logging.info('Result is saved at %s' % self.result_file)
        logging.info(autotest_path)
        logging.info(autotest_dir)

    def _write_result_log(self, msg):
        logging.info(msg)
        self.result_fh.write('%s\n' % msg)

    def _close_result_log(self):
        self.result_fh.close()

    def run_once(self):
        global tdata
        tdata.file_basename = None
        tdata.chrome_request = 0
        tdata.report_finished = False

        # Get functionality_list, and gesture_files_path from config file
        local_path = self.bindir
        functionality_list = read_trackpad_test_conf('functionality_list',
                                                     local_path)

        gesture_files_path_autotest = self.read_gesture_files_path(local_path,
                                      'gesture_files_path_autotest')

        gesture_files_path_results = self.read_gesture_files_path(local_path,
                                     'gesture_files_path_results')

        if not os.path.exists(gesture_files_path_results):
            os.makedirs(gesture_files_path_results)
            logging.info('  The result path "%s" is created successfully.' %
                         gesture_files_path_results)
        self._open_result_log(gesture_files_path_results,
                              gesture_files_path_autotest)

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

        # Get an instance of AutoX to handle X related issues
        autox = cros_ui.get_autox()

        # Start X events capture
        self.xcapture = Xcapture(error, local_path, autox)

        # Initialize X events Check
        self.xcheck = Xcheck(self.tp_device, local_path)

        # Processing every functionality in functionality_list
        # An example functionality is 'any_finger_click'
        for tdata.func in functionality_list:
            # If this function is not enabled in configuration file, skip it.
            if not tdata.func.enabled:
                continue;

            logging.info('\n')
            logging.info('Functionality: %s  (Area: %s)' %
                         (tdata.func.name, tdata.func.area[1]))
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
                # prefix is the area name as default
                tdata.prefix = get_prefix(tdata.func)
                if tdata.prefix is not None:
                    # E.g., prefix = 'click-'
                    prefix = tdata.prefix + '-'
                group_path = os.path.join(gesture_files_path_autotest, prefix)

                if group_name == '*':
                    # E.g., group_path = '.../click-any_finger_click'
                    group_path = group_path + tdata.func.name
                    # Two possibilities of the gesture_file_group:
                    # 1. '.../click-any_finger_click.*':
                    #    variations exists (subname is not None)
                    # 2. '.../click-any_finger_click-*': no variations
                    #    no variations (subname is None)
                    # Note: attributes are separated by dash ('-')
                    #       variations are separated by dot ('.')
                    gesture_file_group = (glob.glob(group_path + '.*') +
                                          glob.glob(group_path + '-*'))
                else:
                    group_path = group_path + group_name
                    gesture_file_group = glob.glob(group_path)

                # Process each specific gesture_file now.
                for gesture_file in gesture_file_group:
                    # Every gesture file name should start with the correct
                    # functionality name, because we use the functionality to
                    # determine the test criteria for the file. Otherwise,
                    # a warning message is shown.
                    tdata.file_basename = os.path.basename(gesture_file)
                    start_flag0 = tdata.file_basename.startswith(
                                  tdata.func.name)
                    start_flag1 = tdata.file_basename.split('-')[1].startswith(
                                  tdata.func.name)
                    if (tdata.prefix is None and not start_flag0) or \
                       (tdata.prefix is not None and not start_flag1):
                        warn_msg = 'The gesture file does not start with ' + \
                                   'correct functionality: %s'
                        logging.warning(warn_msg % gesture_file)
                        tdata.num_wrong_file_name += 1

                    gesture_file_path = os.path.join(
                                    gesture_files_path_autotest, gesture_file)
                    logging.info('')
                    logging.info('    gesture file: %s' % tdata.file_basename)

                    # Start X events capture
                    self.xcapture.start(tdata.file_basename)

                    # Play back the gesture file
                    self.tp_device.playback(gesture_file_path)

                    # Wait until there are no more incoming X events.
                    normal_timeout_flag = self.xcapture.wait()

                    # Stop X events capture
                    self.xcapture.stop()

                    # Check X events
                    tdata.result = self.xcheck.run(tdata.func, tdata,
                                                   self.xcapture.read()) and \
                                   normal_timeout_flag

                    # Update statistics
                    tdata.num_files_tested[tdata.func.name] += 1
                    tdata.tot_num_files_tested += 1
                    if not tdata.result:
                        tdata.fail_count[tdata.func.name] += 1
                        tdata.tot_fail_count += 1

        # Terminate X event capture process
        self.xcapture.terminate()

        # Logging test summary
        self._write_result_log('\n')
        tot_pass_count = tdata.tot_num_files_tested - tdata.tot_fail_count
        msg = ('*** Total number of (passed / tested) files: (%d / %d) ***' %
               (tot_pass_count, tdata.tot_num_files_tested))
        self._write_result_log(msg)
        area_name = None
        for tp_func in functionality_list:
            func_name = tp_func.name
            if tp_func.area[0] != area_name:
                area_name = tp_func.area[0]
                self._write_result_log('  Area: %s' % area_name)
            test_count = tdata.num_files_tested[func_name]
            fail_count = tdata.fail_count[func_name]
            pass_count = test_count - fail_count
            if test_count > 0:
                pass_rate_str = '%3.0f%%' % (100.0 * pass_count / test_count)
                count_str = '(%d / %d)' % (pass_count, test_count)
                pass_str = 'passed.'
            else:
                pass_rate_str = ' '
                count_str = ' '
                pass_str = ''
            func_msg = '      {0:<25}: {1:4s}  {2:9s} '
            msg = func_msg.format(func_name, pass_rate_str, count_str)
            msg += pass_str
            self._write_result_log(msg)
        self._write_result_log('\n')

        # Raise error.TestFail if there is any test failed.
        if tdata.tot_fail_count > 0:
            fail_str = 'Total number of failed files: %d'
            raise error.TestFail(fail_str % tdata.tot_fail_count)
