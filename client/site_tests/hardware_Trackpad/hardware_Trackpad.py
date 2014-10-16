# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

''' Autotest program for verifying trackpad X level driver '''

import glob
import logging
import os
import shutil

import trackpad_util
import trackpad_summary

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

from trackpad_device import TrackpadDevice
from trackpad_util import read_trackpad_test_conf, get_prefix, KEY_LOG, KEY_SEQ
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

    def initialize(self):
        self.vlog = trackpad_util.VerificationLog()
        self.local_path = self.bindir
        self.model = trackpad_util.get_model()
        self.regression_gestures = None
        self.autotest_log_path = trackpad_util.get_logger_filename(
                logging.getLogger(), logging.INFO)

        # Get some parameters from the config file
        self.regression_subset_list = read_trackpad_test_conf(
                'regression_subset_list', self.local_path)
        self.regression_default_subset = read_trackpad_test_conf(
                'regression_default_subset', self.local_path)
        self.functionality_list = read_trackpad_test_conf(
                'functionality_list', self.local_path)
        self.regression_gestures_dict = read_trackpad_test_conf(
                'regression_gestures_dict', self.local_path)

        # Get some file paths from the config file
        self.gesture_files_path_results = self.read_gesture_files_path(
                self.local_path, 'gesture_files_path_results')
        self.gesture_files_subpath_regression = self.read_gesture_files_path(
                self.local_path, 'gesture_files_subpath_regression')
        self.regression_gesture_sets = self.read_gesture_files_path(
                self.local_path, 'regression_gesture_sets')
        self.gesture_files_path_autotest = self.read_gesture_files_path(
                self.local_path, 'gesture_files_path_autotest')
        self.gesture_files_path_latest = self.read_gesture_files_path(
                self.local_path, 'gesture_files_path_latest')

    def read_gesture_files_path(self, local_path, name):
        ''' Read gesture file path from config file. '''
        pathname = read_trackpad_test_conf(name, local_path)
        logging.info('Path of %s: %s' % (name, pathname))
        return pathname

    def _is_in_regression_gestures(self, gesture_file):
        ''' Determine if a gesture file is in the regression gestures list.

        For current settings,
        - long regression test: self.regression_gestures is None, which means
                                all gesture files will be used for regression
                                test.
        - short regression test: self.regression_gestures is read from the file
                                 './data/gestures/regression_gestures_short'
                                 Only gesture files listed in the file will be
                                 used for regression test.

        A gesture file name looks like
            'click-no_cursor_wobble.tap-alex-user-20120430_114910.dat'
        We want to extract the left half part of the file name which looks like
            'click-no_cursor_wobble.tap'
        and check if this gesture exists in the regression_gestures.
        '''
        result = gesture_file.split('-%s-' % self.model)
        gesture = None if result is None else result[0]
        return (self.regression_gestures is None or
                gesture in self.regression_gestures)

    def _extract_tarball_to_work_dir(self, subset):
        ''' Extract the gesture files tarball to working directory '''
        # Set up an empty work directory
        gesture_files_path_work = self.read_gesture_files_path(
                self.local_path, 'gesture_files_path_work')
        if os.path.isdir(gesture_files_path_work):
            shutil.rmtree(gesture_files_path_work, True)
        if not os.path.isdir(gesture_files_path_work):
            os.makedirs(gesture_files_path_work)
            logging.info('  The work path "%s" is created successfully.' %
                         gesture_files_path_work)

        regression_tarball = 'regression_files_%s.tar' % subset
        regression_tarball_path = os.path.join(self.local_path,
                self.gesture_files_subpath_regression, regression_tarball)

        if not os.path.isfile(regression_tarball_path):
            logging.warning('  The regression tarball does not exist: "%s"' %
                         regression_tarball_path)
            return None

        # Extract files from the tarball
        strip_level = 0 if subset == 'short' else 1
        untar_cmd = ('tar --strip-components %d -xvf %s -C %s' %
                     (strip_level,
                      regression_tarball_path,
                      gesture_files_path_work))
        rc = utils.system(untar_cmd)
        if rc != 0:
            logging.warning('  Failed in executing "%s".' % untar_cmd)
            return None
        logging.info('  Succeeded in executing "%s".' % untar_cmd)
        return gesture_files_path_work

    def _set_regression_gestures(self, subset):
        ''' Read regression_gestures based on the subset

        When self.regression_gestures is set to None, it means that all of the
        gesture files in the specified gesture set will be used.
        '''
        if subset is None or self.regression_gestures_dict[subset] is None:
            self.regression_gestures = None
        else:
            gestures_path = os.path.join(self.local_path,
                                         self.regression_gestures_dict[subset])
            execfile(gestures_path, globals())
            if self.model in regression_gestures:
                self.regression_gestures = regression_gestures[self.model]
            else:
                self.regression_gestures = baseline_regression_gestures

    def _get_regression_gesture_set(self, subset):
        ''' Get the regression gesture set. '''
        model = self.model
        if subset not in self.regression_subset_list:
            subset = self.regression_default_subset

        # Skip those models that are not specified the regression gesture sets.
        # There are two possible reasons:
        #   (1) the gestures are not captured yet.
        #   (2) it is a model without built-in trackpad.
        if model not in self.regression_gesture_sets[subset]:
            return None

        regression_gesture_set = self.regression_gesture_sets[subset][model]
        gesture_set_path = os.path.join(self.local_path,
                self.gesture_files_subpath_regression, regression_gesture_set)

        # Make a symlink for autotest.
        trackpad_util.write_symlink(gesture_set_path,
                                    self.gesture_files_path_autotest)

        return subset

    def _setup_gesture_files_path(self, test_set, subset):
        ''' Set up gesture files path

        If it is a tarball, extract files from the tarball and set up its path.
        If it is an ordinary directory, just returns its path.
        '''
        # If this is a regression test, let gesture_files_path_autotest
        # point to the regression gesture set specified in conf.
        if test_set == 'regression':
            subset = self._get_regression_gesture_set(subset)

        # If this is a test on a gesture set captured in the local machine,
        # let gesture_files_path_autotest point to the 'latest' symlink if it
        # exists. Otherwise, let it point to the default regression gesture set.
        elif test_set == 'localhost':
            if os.path.exists(self.gesture_files_path_latest):
                trackpad_util.write_symlink(self.gesture_files_path_latest,
                                            self.gesture_files_path_autotest)
                subset = 'long'
            else:
                subset = self._get_regression_gesture_set(subset)

        # Skip those models without the regression gesture sets.
        if subset is None:
            return None

        # Determine gestures to test
        self._set_regression_gestures(subset)

        logging.info('  test_set: %s' % test_set)
        logging.info('  subset: %s' % subset)
        logging.info('  gesture_files_path_autotest: %s' %
                     os.path.realpath(self.gesture_files_path_autotest))

        return self.gesture_files_path_autotest

    def run_once(self, test_set='localhost', subset=None):
        ''' test_set determines the path of gesture files.

        The test_set could be
            localhost: run locally from the client side
            regression: run by control.regression
        '''
        utils.assert_has_X_server()
        global tdata
        tdata.file_basename = None
        tdata.chrome_request = 0
        tdata.report_finished = False
        local_path = self.local_path
        functionality_list = self.functionality_list
        gesture_files_path_results = self.gesture_files_path_results

        # Set up regression path
        gesture_files_path_autotest = self._setup_gesture_files_path(test_set,
                                                                     subset)

        # Skip those models without regression gesture sets.
        if gesture_files_path_autotest is None:
            logging.info('No gesture sets are specified for this model: %s' %
                         self.model)
            return

        # Exit if the gesture files path for autotest does not exist.
        if (gesture_files_path_autotest is None or
            not os.path.exists(gesture_files_path_autotest)):
            raise error.TestError('  The autotest path does not exist: %s.' %
                    str(os.path.realpath(gesture_files_path_autotest)))

        if not os.path.exists(gesture_files_path_results):
            os.makedirs(gesture_files_path_results)
            logging.info('  The result path "%s" is created successfully.' %
                         gesture_files_path_results)
        self.ilog = trackpad_util.IterationLog(gesture_files_path_results,
                                               gesture_files_path_autotest,
                                               self.autotest_log_path)

        # Start tpcontrol log and get the gesture library version
        self.tpcontrol_log = trackpad_util.TpcontrolLog()
        gesture_version = self.tpcontrol_log.get_gesture_version()
        logging.info('Gesture library version: %s' % gesture_version)

        # Initialization of statistics
        tdata.num_wrong_file_name = 0
        tdata.num_files_tested = {}
        tdata.num_files_tested_fullname = {}
        tdata.subname_list = {}
        tdata.tot_fail_count = 0
        tdata.tot_num_files_tested = 0
        tdata.fail_count = dict([(tp_func.name, 0)
                                 for tp_func in functionality_list])
        tdata.fail_count_fullname = {}
        vlog_dict = {}
        vlog_dict[KEY_LOG] = {}
        vlog_dict[KEY_SEQ] = []
        logging.info('')
        logging.info('*** hardware_Trackpad autotest is started ***')

        # Start Trackpad Input Device
        self.tp_device = TrackpadDevice()

        # Start X events capture
        self.xcapture = Xcapture(error, local_path)

        # Initialize X events Check
        self.xcheck = Xcheck(self.tp_device, local_path)

        # Processing every functionality in functionality_list
        # An example functionality is 'any_finger_click'
        for tdata.func in functionality_list:
            flag_logging_func_name = False
            tdata.num_files_tested[tdata.func.name] = 0
            tdata.subname_list[tdata.func.name] = []

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
                    group_path += tdata.func.name
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
                    group_path += group_name
                    gesture_file_group = glob.glob(group_path)

                # Process each specific gesture_file now.
                for gesture_file in gesture_file_group:
                    tdata.file_basename = os.path.basename(gesture_file)
                    # If regression_gestures have been specified, this file
                    # should be in the regression_gestures.
                    # Currently, the short regression test has been specified
                    # the regression_gestures.
                    if not self._is_in_regression_gestures(tdata.file_basename):
                        continue

                    # Every gesture file name should start with the correct
                    # functionality name, because we use the functionality to
                    # determine the test criteria for the file. Otherwise,
                    # a warning message is shown.
                    start_flag0 = tdata.file_basename.startswith(
                                  tdata.func.name)
                    start_flag1 = tdata.file_basename.split('-')[1].startswith(
                                  tdata.func.name)
                    if ((tdata.prefix is None and not start_flag0) or
                        (tdata.prefix is not None and not start_flag1)):
                        warn_msg = ('The gesture file does not start with '
                                    'correct functionality: %s')
                        logging.warning(warn_msg % gesture_file)
                        tdata.num_wrong_file_name += 1

                    gesture_file_path = os.path.join(
                        gesture_files_path_autotest, gesture_file)

                    if not flag_logging_func_name:
                        flag_logging_func_name = True
                        logging.info('\nFunctionality: %s  (Area: %s)' %
                                     (tdata.func.name, tdata.func.area[1]))
                    logging.info('\n    gesture file: %s' % tdata.file_basename)

                    # Start X events capture
                    self.xcapture.start(tdata.file_basename)

                    # Play back the gesture file
                    self.tp_device.playback(gesture_file_path)

                    # Wait until there are no more incoming X events.
                    normal_timeout_flag = self.xcapture.wait()

                    # Stop X events capture
                    self.xcapture.stop()

                    # Check X events
                    xevent_str = self.xcapture.read()
                    output = self.xcheck.run(tdata.func, tdata, xevent_str)
                    tdata.result = output['result'] and normal_timeout_flag

                    # Insert the verification log into the vlog dictionary
                    self.vlog.insert_vlog_dict(vlog_dict, gesture_file,
                                               output['result'], output['vlog'])

                    logging.info('...................vlog.................')
                    logging.info(str(output['vlog']))

                    # Save tpcontrol log if this gesture file failed.
                    if not tdata.result:
                        self.tpcontrol_log.save_log(tdata.file_basename)

                    # Initialization for this subname
                    fullname = trackpad_util.get_fullname(tdata.file_basename)
                    if not tdata.subname_list[tdata.func.name]:
                        tdata.subname_list[tdata.func.name] = []
                    if fullname not in tdata.num_files_tested_fullname:
                        tdata.num_files_tested_fullname[fullname] = 0
                        tdata.subname_list[tdata.func.name].append(fullname)
                        tdata.fail_count_fullname[fullname] = 0

                    # Update statistics
                    tdata.num_files_tested[tdata.func.name] += 1
                    tdata.num_files_tested_fullname[fullname] += 1
                    tdata.tot_num_files_tested += 1
                    if not tdata.result:
                        tdata.fail_count[tdata.func.name] += 1
                        tdata.fail_count_fullname[fullname] += 1
                        tdata.tot_fail_count += 1

        # Terminate X event capture process
        self.xcapture.terminate()

        # Logging test summary
        tot_pass_count = tdata.tot_num_files_tested - tdata.tot_fail_count
        msg = trackpad_summary.format_result_header(self.ilog.result_file_name,
                                                    tot_pass_count,
                                                    tdata.tot_num_files_tested)
        self.ilog.write_result_log(msg)

        area_name = None
        for tp_func in functionality_list:
            # if not tp_func.enabled:
            #     continue
            func_name = tp_func.name
            test_count = tdata.num_files_tested[func_name]
            if test_count == 0:
                continue
            if tp_func.area[0] != area_name:
                area_name = tp_func.area[0]
                msg = trackpad_summary.format_result_area(area_name)
                self.ilog.write_result_log(msg)

            for fullname in tdata.subname_list[func_name]:
                test_count_fullname = tdata.num_files_tested_fullname[fullname]
                fail_count_fullname = tdata.fail_count_fullname[fullname]
                pass_count_fullname = test_count_fullname - fail_count_fullname
                msg = trackpad_summary.format_result_pass_rate(fullname,
                      pass_count_fullname, test_count_fullname)
                self.ilog.write_result_log(msg)

        msg = trackpad_summary.format_result_tail()
        self.ilog.write_result_log(msg)
        self.ilog.write_result_log('Verification Log = %s' % vlog_dict)
        self.ilog.write_result_log('\n\n\n')
        self.ilog.close_result_log()
        self.ilog.append_detailed_log(self.autodir)

        # Raise error.TestFail if there is any test failed.
        if tdata.tot_fail_count > 0:
            fail_str = 'Total number of failed files: %d'
            raise error.TestFail(fail_str % tdata.tot_fail_count)
