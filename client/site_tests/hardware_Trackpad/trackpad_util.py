# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

''' Trackpad utility program for reading test configuration data '''

import glob
import logging
import os
import re
import shutil
import time

import common_util
import cros_gestures_lib
import Xevent


record_program = 'evemu-record'
trackpad_test_conf = 'trackpad_usability_test.conf'
trackpad_device_file_hardcoded = '/dev/input/event6'
autodir = '/usr/local/autotest'
autotest_program = os.path.join(autodir, 'bin/autotest')
autotest_log_subpath = 'results/default/debug/client.0.INFO'
conf_file_executed = False
time_format = '%Y%m%d_%H%M%S'

# The following two key definitions will be used in verification log
# related dictionaries: vlog_dict and gss_vlog_dict.
KEY_LOG = 'log'
KEY_SEQ = 'seq'


def debug(msg, level=2):
    debug_level = 1
    if level <= debug_level:
        logging.info(msg)


class TrackpadTestFunctionality:
    ''' Define the attributes of test functionality

    name: functionality name, e.g., any_finger_click
    subname: additional property for the name
            e.g., up or down for two_finger_scroll
    description: description of the functionality
    prompt, subprompt: Prompt messages about a functionality and its subname
            when recording
    area: functionality area. e.g., '1 finger point & click'
    criteria: configurable criteria associated with a particular functionality
    weight: the weight of each functionality, used to calculate how well a
            driver performs
    enabled: True or False to indicate if this functionality is enabled for
            testing
    files: the test files for the functionality
    '''

    def __init__(self, name=None, subname=None, description=None, prompt=None,
                 subprompt=None, area=None, criteria=None, weight=1,
                 enabled=True, files=None):
        self.name = name
        self.subname = subname
        self.description = description
        self.prompt = prompt
        self.subprompt = subprompt
        self.area = area
        self.criteria = criteria
        self.weight = weight
        self.enabled = enabled
        self.files = files


class Display:
    ''' A simple class to handle display environment and set cursor position '''
    DISP_STR = ':0'
    XAUTH_STR = '/home/chronos/.Xauthority'

    def __init__(self):
        self._setup_display()

    def _setup_display(self):
        import Xlib
        import Xlib.display
        self.set_environ()
        self.disp = Xlib.display.Display(Display.DISP_STR)
        self.screen = self.disp.screen()
        self.root = self.screen.root
        self.calc_center()

    def get_environ(self):
        ''' Get DISPLAY and XAUTHORITY '''
        disp_str = 'DISPLAY=%s' % Display.DISP_STR
        xauth_str = 'XAUTHORITY=%s' % Display.XAUTH_STR
        display_environ = ' '.join([disp_str, xauth_str])
        return display_environ

    def set_environ(self):
        ''' Set DISPLAY and XAUTHORITY '''
        os.environ['DISPLAY'] = Display.DISP_STR
        os.environ['XAUTHORITY'] = Display.XAUTH_STR

    def calc_center(self):
        ''' Calculate the center of the screen '''
        self.center = (self.screen.width_in_pixels / 2,
                       self.screen.height_in_pixels / 2)

    def move_cursor_to_center(self):
        ''' Move the cursor to the center of the screen '''
        self.root.warp_pointer(*self.center)
        self.disp.sync()


class IterationLog:
    ''' Maintain the log for an iteration '''

    def __init__(self, result_path, autotest_gs_symlink,
                 autotest_log_path=None):
        self.open_result_log(result_path, autotest_gs_symlink)
        self.autotest_log_path = autotest_log_path

    def open_result_log(self, result_path, autotest_gs_symlink):
        test_time = 'tested:' + time.strftime(time_format, time.gmtime())
        autotest_gs_name = os.path.realpath(autotest_gs_symlink).split('/')[-1]
        self.result_file_name = '.'.join([autotest_gs_name, test_time])
        self.result_file = os.path.join(result_path, self.result_file_name)
        self.result_fh = open(self.result_file, 'w+')
        logging.info('Gesture set tested: %s', autotest_gs_name)
        logging.info('Result is saved at %s' % self.result_file)

    def write_result_log(self, msg):
        logging.info(msg)
        self.result_fh.write('%s\n' % msg)

    def close_result_log(self):
        self.result_fh.close()

    def append_detailed_log(self, autodir):
        if self.autotest_log_path is None:
            self.autotest_log_path = os.path.join(autodir, autotest_log_subpath)
        append_cmd = 'cat %s >> %s' % (self.autotest_log_path, self.result_file)
        try:
            common_util.simple_system(append_cmd)
            logging.info('Append detailed log: "%s"' % append_cmd)
        except:
            logging.warning('Warning: fail to execute "%s"' % append_cmd)


class VerificationLog:
    ''' Maintain the log when verifying various X events '''

    def __init__(self):
        self.button_labels = Xevent.XButton().get_supported_buttons()
        self.RESULT_STR = {True : 'Pass', False : 'Fail'}
        self.log = {}

    def verify_motion_log(self, result_flag, sum_move):
        result_str = self.RESULT_STR[result_flag]
        logging.info('        Verify motion: (%s)' % result_str)
        logging.info('              Total movement = %d' % sum_move)
        if not result_flag:
            self.log['motion'] = sum_move

    def verify_button_log(self, result_flag, count_buttons):
        result_str = self.RESULT_STR[result_flag]
        logging.info('        Verify button: (%s)' % result_str)
        button_msg_details = '              %s: %d times'
        count_flag = False
        button_log_dict = {}
        for idx, b in enumerate(self.button_labels):
            if count_buttons[idx] > 0:
                logging.info(button_msg_details % (b, count_buttons[idx]))
                button_log_dict[b] = count_buttons[idx]
                count_flag = True
        if not count_flag:
            logging.info('              No Button events detected.')
        if not result_flag:
            self.log['button'] = button_log_dict

    def verify_sequence_log(self, result_flag, seq, fail_msg, fail_para):
        result_str = self.RESULT_STR[result_flag]
        logging.info('        Verify select sequence: (%s)' % result_str)
        logging.info('              Detected event sequence')
        for e in seq:
            logging.info('                      ' + str(e))
        if not result_flag:
            logging.info('              ' + fail_msg % fail_para)
        if not result_flag:
            self.log['sequence'] = seq

    def verify_button_dev_log(self, result_flag, button_dev, fail_msg,
                              target_button, button_count, crit_button_count):
        result_str = self.RESULT_STR[result_flag]
        logging.info('        Verify button_dev: (%s)' % result_str)
        logging.info('              Detected event sequence')
        for e in button_dev:
            logging.info('                      ' + str(e))

        logging.info('              ' + 'Detected button count:')
        msg = 'Count[%s] = %d, Criteria = %d' % (target_button, button_count,
                                                 crit_button_count)
        button_count_msg = '                  ' + msg
        logging.info(button_count_msg)

        if not result_flag:
            logging.info('              Failed causes:')
            for m in fail_msg:
                logging.info('                  ' + m)
        if not result_flag:
            self.log['button_dev'] = fail_msg

    def verify_button_segment_log(self, result_flag, button_seg, fail_msg,
                                  fail_para):
        result_str = self.RESULT_STR[result_flag]
        logging.info('        Verify button_segment: (%s)' % result_str)
        logging.info('              Detected event sequence')
        for e in button_seg:
            logging.info('                      ' + str(e))
        if not result_flag:
            logging.info('              ' + fail_msg % fail_para)
            self.log['button_segment'] = button_seg

    def insert_vlog_dict(self, vlog_dict, gesture_file, vlog_result, vlog_log):
        ''' Insert the verification log in a dictionary '''
        gesture_name = extract_gesture_name_from_file(gesture_file)
        gesture_file_realpath = os.path.realpath(gesture_file)

        # Keep the root_cause only when it failed.
        if not vlog_result:
            vlog_dict[KEY_LOG][gesture_name] = {}
            vlog_dict[KEY_LOG][gesture_name]['file'] = gesture_file_realpath
            vlog_dict[KEY_LOG][gesture_name]['root_cause'] = vlog_log

        if gesture_name not in vlog_dict[KEY_SEQ]:
            vlog_dict[KEY_SEQ].append(gesture_name)


def extract_gesture_name_from_file(filename):
    ''' Extract the functionality name plus subname from a gesture file

    For example,
    a file name:
        click-no_cursor_wobble.physical_click-alex-mary-20111213_210402.dat
    Its corresponding gesture name:
        click-no_cursor_wobble.physical_click
    '''
    gesture_file_basename = os.path.basename(filename)
    gesture_name = '-'.join(gesture_file_basename.split('-')[0:2])
    return gesture_name


def read_trackpad_test_conf(target_name, path):
    ''' Read target item from the configuration file

    target_name: a target variable to read, e.g., 'functionality_list'
    path: the path of the configuration file

    This function parses the configuration file to derive the target variable.
    Once having parsed the configuration file, this module has obtained all
    configuration variables. This module will keep all such variables in its
    global space. Next time this function is called, a variable can be returned
    immediately without parsing the configuration file again.
    '''
    global conf_file_executed
    if not conf_file_executed:
        trackpad_test_conf_path = os.path.join(path, trackpad_test_conf)
        execfile(trackpad_test_conf_path, globals())
        conf_file_executed = True
    return eval(target_name)


def get_prefix(func):
    ''' Get the prefix string in filename attributes '''
    attrs = read_trackpad_test_conf('filename_attr', '.')
    for attr in attrs:
        if attr[0] == 'prefix':
            return func.area[0] if attr[1] == 'DEFAULT' else attr[1]


def file_exists(filename):
    ''' Verify the existence of a file '''
    return (filename if filename is not None and os.path.exists(filename)
                     else None)


def get_trackpad_re_str():
    ''' Get the trackpad device string in regular expression. '''
    trackpad_str = read_trackpad_test_conf('xinput_trackpad_string', '.')
    trackpad_re_str = '(?:%s)' % '|'.join(trackpad_str)
    return trackpad_re_str


def _probe_trackpad_device_file():
    ''' Probe trackpad device file in /proc/bus/input/devices '''
    device_info = '/proc/bus/input/devices'
    if not os.path.exists(device_info):
        return None
    with open(device_info) as f:
        device_str = f.read()
    device_iter = iter(device_str.splitlines())
    trackpad_pattern = re.compile('name=.+%s' % get_trackpad_re_str(), re.I)
    event_pattern = re.compile('handlers=.*event(\d+)', re.I)
    found_trackpad = False
    trackpad_device_file = None
    while True:
        line = next(device_iter, None)
        if line is None:
            break
        if not found_trackpad and trackpad_pattern.search(line) is not None:
            found_trackpad = True
        elif found_trackpad:
            res = event_pattern.search(line)
            if res is not None:
                event_no = int(res.group(1))
                file_str = '/dev/input/event%d' % event_no
                trackpad_device_file = file_exists(file_str)
                break
    return trackpad_device_file


def get_trackpad_device_file():
    ''' Get and verify trackpad device file

        Priority 1: Probe the trackpad device in the system. If the probed
                    trackpad device file exists
        Priority 2: if trackpad_device_file in the configuration file is
                    defined and the file exists
        Priority 3: if the trackpad device file cannot be determined above,
                    using the hard coded one in trackpad_util
    '''
    # Probe the trackpad device file in the system
    file_probed = _probe_trackpad_device_file()

    # Read and verify the existence of the configured device file
    config_dev = read_trackpad_test_conf('trackpad_device_file', '.')
    file_config = file_exists(config_dev)

    # Read and verify the existence of the hard coded device file
    hard_dev = trackpad_device_file_hardcoded
    file_hardcoded = file_exists(hard_dev)

    if file_probed is not None:
        trackpad_device_file = file_probed
        msg = 'Probed device file: %s' % file_probed
    elif file_config is not None:
        trackpad_device_file = file_config
        msg = 'The device file in %s: %s' % (trackpad_test_conf, file_config)
    elif file_hardcoded is not None:
        trackpad_device_file = file_hardcoded
        msg = 'The device hard coded in trackpad_util: %s' % file_hardcoded
    else:
        trackpad_device_file = None
        msg = 'The trackpad device file is not available!'
    return (trackpad_device_file, msg)


def get_model():
    ''' Get model (board) of the Chromebook machine. '''
    with open('/etc/lsb-release') as f:
        context = f.read()
    model = 'unknown_model'
    if context is not None:
        for line in context.splitlines():
            if line.startswith('CHROMEOS_RELEASE_BOARD'):
                board_str = line.split('=')[1]
                if '-' in board_str:
                    model = board_str.split('-')[1]
                elif '_' in board_str:
                    model = board_str.split('_')[1]
                else:
                    model = board_str
                # Some models, e.g. alex, may have board name as alex32
                model = re.search('(\D+)\d*', model, re.I).group(1)
                break
    return model


def _create_dir(data_dir):
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print '  %s is created successfully.' % data_dir


def setup_tester_gesture_set(tester, flag_continue):
    ''' Set up a gesture set path for a tester or create a new directory. '''
    # Get the root path storing gesture sets (gss)
    gss_root = read_trackpad_test_conf('gesture_files_path_root', '.')
    gss_latest = read_trackpad_test_conf('gesture_files_path_latest', '.')

    # Get the tester's latest gesture set or create a new one
    tester_gs_search = os.path.join(gss_root, tester) + '*'
    all_tester_gs = glob.glob(tester_gs_search)
    if flag_continue and all_tester_gs:
        tester_gs = reduce(lambda x, y: x if x >= y else y, all_tester_gs)
    else:
        tester_gs_base = '_'.join([tester, time.strftime(time_format,
                                                         time.gmtime())])
        tester_gs = os.path.join(gss_root, tester_gs_base)

    # Create tester gesture set if it does not exist yet.
    _create_dir(tester_gs)

    # Make the 'latest' link in gss_root point to tester_gs.
    # Should use islink() rather than exists() here for a symbolic link.
    if os.path.islink(gss_latest):
        os.remove(gss_latest)
    os.symlink(tester_gs, gss_latest)
    print 'Gesture files will be stored in the gesture set: %s.' % tester_gs

    return tester_gs


class TpcontrolLog:
    ''' Handles tpcontrol log '''

    def __init__(self):
        tpcontrol_log_cmd = '/opt/google/touchpad/tpcontrol log'
        self.original_log_dir = '/home/chronos/user/log'
        self.latest_log_file = '/var/log/touchpad_activity_log.txt'
        trackpad_test_dir = '/var/tmp/trackpad_test_data'
        self.tmp_log_dir = os.path.join(trackpad_test_dir, 'old_tpcontrol_log')
        self.new_log_dir = os.path.join(trackpad_test_dir, 'tpcontrol_log')
        self.log_prefix = 'touchpad_activity*'
        self.log_ext = '.tpcontrol_log.gz'
        self.tar_dir = os.path.join(trackpad_test_dir, 'tpcontrol_log_tar')
        self.tar_path = os.path.join(self.tar_dir, 'tpcontrol_log_tar')
        display_environ = Display().get_environ()
        self.tpcontrol_log_cmd = ' '.join([display_environ, tpcontrol_log_cmd])
        self.all_dirs = [self.original_log_dir, self.tmp_log_dir,
                         self.new_log_dir, self.tar_dir]

        # Create the log directory if not existent yet
        for p in self.all_dirs:
            if not os.path.isdir(p):
                logging.info('Create tpcontrol log directory: %s' % p)
                os.makedirs(p)

    def save_log(self, file_name):
        ''' Save tpcontrol log file '''
        # Move any existent log files
        existent_log_files = glob.glob(os.path.join(self.original_log_dir,
                                                    self.log_prefix))
        if existent_log_files:
            for f in existent_log_files:
                src_f_path = os.path.join(self.original_log_dir, f)
                msg = '  Move the log file "%s" to "%s"'
                logging.info(msg % (f, self.tmp_log_dir))
                shutil.move(src_f_path, self.tmp_log_dir)

        # Create tpcontrol log file
        common_util.simple_system(self.tpcontrol_log_cmd)
        log_file_list = glob.glob(os.path.join(self.original_log_dir,
                                               self.log_prefix))
        num_log_files = len(log_file_list)
        if num_log_files == 0:
            logging.warning('  tpcontrol log file is not generated.')
        elif num_log_files > 1:
            logging.warning('  Multiple (%d) tpcontrol log files were generated.' %
                         num_log_files)
        else:
            # Convert the file name from xxx.dat to xxx.tpcontrol_log.gz
            basename = os.path.basename(file_name)
            new_log_file_name = os.path.splitext(basename)[0] + self.log_ext
            new_log_file_path = os.path.join(self.new_log_dir,
                                             new_log_file_name)
            # Move the log file to the new path
            original_log_file_path = os.path.join(self.original_log_dir,
                                                  log_file_list[0])
            logging.info('  tpcontrol log file: from %s to %s' %
                         (original_log_file_path, new_log_file_path))
            shutil.move(original_log_file_path, new_log_file_path)

    def tar_tpcontrol_logs(self):
        ''' tar the tpcontrol logs '''
        tar_cmd = 'tar -jcvf %s.tar.bz2 %s' % (self.tar_path, self.new_log_dir)
        logging.info('  The tar ball of tpcontrol log files is saved in %s' %
                     self.tar_path)
        common_util.simple_system(tar_cmd)

    def get_gesture_version(self):
        ''' Extract the gesture library version from the tpcontrol log '''
        # Generate tpcontrol log and confirm its existence
        common_util.simple_system(self.tpcontrol_log_cmd)
        if not os.path.isfile(self.latest_log_file):
            return None

        # Extract the version string from the tpcontrol log
        # The gesture library version in tpcontrol log looks like
        # "gesturesVersion": "0.0.1-r86-f821a04bb5487f24efe0bd2952abd0a23fe68e"
        version = re.compile('"gesturesVersion":\s*"(.*)"')
        with open(self.latest_log_file) as f:
            for line in f:
                result = version.search(line)
                if result is not None:
                    return result.group(1)
        return None


def get_fullname(filename):
    ''' Extract the fullname (func name + subname) from a gesture file name '''
    return filename.split('-')[1]


def _create_dir_meta_name(gesture_path, extra_name_code, dir_code):
    ''' Create a meta data file holding the file names in a given path

    An example meta data file name looks like:
            mix-dir.all-alex-john_tut1-20111216_000547.dat
    where 'alex' is the user name, and 'john_tut1-20111216_000547' is the
    target directory name.
    '''
    model = get_model()
    patt = '%s_' % extra_name_code
    repl = '%s-' % extra_name_code
    dir_name = os.path.realpath(gesture_path).split('/')[-1]
    dir_name = re.sub(patt, repl, dir_name)
    dir_meta_name = '%s-%s-%s.dat' % (dir_code, model, dir_name)
    return dir_meta_name


def _create_dir_file(gesture_path, extra_name_code, mix_code, dir_code):
    ''' Create a directory file containing gesture file names and misc info '''

    # Get gesture files
    gesture_files = glob.glob(os.path.join(gesture_path, '*'))
    lambda_exclude = lambda f: not f.split('/')[-1].startswith(mix_code)
    gesture_files = filter(lambda_exclude, gesture_files)

    # Get WiFi hardware address
    hw_addr = 'unknown'
    cmd_if = 'ifconfig | grep HWaddr'
    hw_addr_str = common_util.simple_system_output(cmd_if)
    if hw_addr is not None:
        m = re.search('HWaddr\s+(.*)', hw_addr_str)
        if m is not None:
            hw_addr = m.group(1)

    # Get chromeos lsb information
    chromeos_description = 'unknown'
    chromeos_devserver = 'unknown'
    with open('/etc/lsb-release') as f:
        context = f.read()
    if context is not None:
        for line in context.splitlines():
            if line.startswith('CHROMEOS_RELEASE_DESCRIPTION'):
                chromeos_description = line
            elif line.startswith('CHROMEOS_DEVSERVER'):
                chromeos_devserver = line

    # Create the directory file
    dir_meta_name = _create_dir_meta_name(gesture_path, extra_name_code,
                                          dir_code)
    dir_meta_file = os.path.join(gesture_path, dir_meta_name)
    hw_addr_format = '# WiFi hardware address=%s\n'
    chromeos_description_format = '# CHROMEOS_RELEASE_DESCRIPTION=%s\n'
    chromeos_devserver_format = '# CHROMEOS_DEVSERVER=%s\n'
    with open(dir_meta_file, 'w') as f:
        for filename in gesture_files:
            # filename includes path information
            f.write(filename + '\n')
        f.write('\n\n')
        f.write(hw_addr_format % hw_addr)
        f.write(chromeos_description_format % chromeos_description)
        f.write(chromeos_devserver_format % chromeos_devserver)


def gs_upload_gesture_set(gesture_path, autotest_dir, extra_name_code,
                          mix_code, dir_code):
    ''' Upload a gesture set to google storage through cros_gestures_lib '''
    # Create a directory file containing gesture file names and misc information
    _create_dir_file(gesture_path, extra_name_code, mix_code, dir_code)

    # Upload the gesture files
    gesture_lib = cros_gestures_lib.CrosGesturesLib(autotest_dir)
    rc = gesture_lib.upload_files()
    if rc != 0:
        print 'Error in uploading gesture files in %s.' % gesture_path
    return rc


def write_symlink(source, link_name):
    ''' Make the link point to the source. '''
    if os.path.islink(link_name):
        os.remove(link_name)
    elif os.path.isdir(link_name):
        shutil.rmtree(link_name, True)
    else:
        parent_dir = os.path.dirname(link_name)
        if not os.path.isdir(parent_dir):
            os.makedirs(parent_dir)
    os.symlink(source, link_name)


def get_logger_filename(logger, level):
    ''' Get the handler filename with the specified level from logger '''
    for handler in logger.handlers:
        if handler.level == level:
            return handler.baseFilename
    return None
