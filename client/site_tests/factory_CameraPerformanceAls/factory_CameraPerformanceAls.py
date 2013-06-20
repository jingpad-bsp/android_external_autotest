# -*- coding: utf-8; tab-width: 4; python-indent: 4 -*-
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Import guard for OpenCV.
try:
    import cv
    import cv2
except ImportError:
    pass

import base64
import numpy as np
import os
import pprint
import pyudev
import re
import select
import serial
import signal
import StringIO
import subprocess
import threading
import time

import autotest_lib.client.cros.camera.perf_tester as camperf
import autotest_lib.client.cros.camera.renderer as renderer

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory_setup_modules
from cros.factory.event_log import Log
from cros.factory.test import factory
from cros.factory.test import leds
from cros.factory.test import test_ui
from cros.factory.test.media_util import MountedMedia
from cros.factory.utils.process_utils import SpawnOutput
from autotest_lib.client.cros.rf.config import PluggableConfig
from autotest_lib.client.cros import tty
from cros.factory.test.test_ui import UI


# Test type constants:
_TEST_TYPE_MODULE = 'Module'
_TEST_TYPE_AB = 'AB'
_TEST_TYPE_FULL = 'Full'

# Content type constants:
_CONTENT_IMG = 'image'
_CONTENT_TXT = 'text'


class ALS():
    '''Class to interface the ambient light sensor over iio.'''

    # Default device paths.
    _VAL_DEV_PATH = '/sys/bus/iio/devices/iio:device0/illuminance0_input'
    _SCALE_DEV_PATH = '/sys/bus/iio/devices/iio:device0/illuminance0_calibscale'

    # Default min delay seconds.
    _DEFAULT_MIN_DELAY = 0.178

    def __init__(self, val_path=_VAL_DEV_PATH,
                 scale_path=_SCALE_DEV_PATH):
        self.detected = True
        if (not os.path.isfile(val_path) or
            not os.path.isfile(scale_path)):
            self.detected = False
            return
        self.val_path = val_path
        self.scale_path = scale_path

    def _read_core(self):
        fd = open(self.val_path)
        val = int(fd.readline().rstrip())
        fd.close()
        return val

    def _read(self, delay=None, samples=1):
        '''Read the light sensor value.

        Args:
            delay: Delay between samples in seconds. 0 means as fast as
                   possible.
            samples: Total samples to read.

        Returns:
            The light sensor values in a list.
        '''
        if samples < 1:
            samples = 1
        if delay is None:
            delay = self._DEFAULT_MIN_DELAY

        buf = []
        # The first value might be contaminated by previous settings.
        # We need to skip it for better accuracy.
        self._read_core()
        for dummy in range(samples):
            time.sleep(delay)
            val = self._read_core()
            buf.append(val)

        return buf

    def read_mean(self, delay=None, samples=1):
        if not self.detected:
            return None

        buf = self._read(delay, samples)
        return int(round(float(sum(buf)) / len(buf)))

    def set_scale_factor(self, scale):
        if not self.detected:
            return None

        fd = open(self.scale_path, 'w')
        fd.write(str(int(round(scale))))
        fd.close()
        return

    def get_scale_factor(self):
        if not self.detected:
            return None

        fd = open(self.scale_path)
        s = int(fd.readline().rstrip())
        fd.close()
        return s


class FixtureException(Exception):
  pass


class Fixture():
    '''Class for communication with the test fixture.'''

    def __init__(self, params):
        # Setup the serial port communication.
        tty_path = tty.find_tty_by_driver(params['driver'])
        self.fixture = serial.Serial(port=tty_path,
                                     **params['serial_params'])
        self.fixture.flush()

        # Load parameters.
        self.serial_delay = params['serial_delay']
        self.light_delay = params['light_delay']
        self.light_seq = params['light_seq']
        self.fixture_echo = params['echo']
        self.light_off = params['off']

    def send(self, msg):
        '''Send control messages to the fixture.'''
        for c in msg:
            self.fixture.write(str(c))
            self.fixture.flush()
            # The fixture needs some time to process each incoming character.
            time.sleep(self.serial_delay)

    def read(self):
        return self.fixture.read(self.fixture.inWaiting())

    def assert_success(self):
        '''Check if the returned value from the fixture is OK.'''
        ret = self.read()
        if not re.search(self.fixture_echo, ret):
            raise FixtureException('The communication with fixture was broken')

    def set_light(self, idx):
        self.send(self.light_seq[idx])

    def turn_off_light(self):
        self.send(self.light_off)

    def wait_for_light_switch(self):
        time.sleep(self.light_delay)


class ConnectionMonitor():
    """A wrapper to monitor hardware plug/unplug events."""
    def __init__(self):
        self._monitoring = False

    def start(self, subsystem, device_type=None, on_insert=None,
              on_remove=None):
        if self._monitoring:
            raise Exception("Multiple start() call is not allowed")
        self.on_insert = on_insert
        self.on_remove = on_remove

        # Setup the media monitor,
        context = pyudev.Context()
        self.monitor = pyudev.Monitor.from_netlink(context)
        self.monitor.filter_by(subsystem, device_type)
        self.monitor.start()
        self._monitoring = True
        self._watch_thread = threading.Thread(target=self.watch)
        self._watch_end = threading.Event()
        self._watch_thread.start()

    def watch(self):
        fd = self.monitor.fileno()
        while not self._watch_end.isSet():
            ret, _, _ = select.select([fd],[],[])
            if fd in ret:
                action, dev = self.monitor.receive_device()
                if action == 'add' and self.on_insert:
                    self.on_insert(dev.device_node)
                elif action == 'remove' and self.on_remove:
                    self.on_remove(dev.device_node)

    def stop(self):
        self._monitoring = False
        self._watch_end.set()


class factory_CameraPerformanceAls(test.test):
    version = 2
    preserve_srcdir = True

    _TEST_CHART_FILE = 'test_chart.png'
    _TEST_SAMPLE_FILE = 'sample.png'
    _BAD_SERIAL_NUMBER = 'BAD_SN'
    _NO_SERIAL_NUMBER = 'NO_SN'

    _PACKET_SIZE = 65000

    # Status in the final result tab.
    _STATUS_NAMES = ['cam_stat', 'cam_vc', 'cam_ls', 'cam_mtf',
                     'als_stat', 'result']
    _STATUS_LABELS = ['Camera Functionality',
                      'Camera Visual Correctness',
                      'Camera Lens Shading',
                      'Camera Image Sharpness',
                      'ALS Functionality',
                      'Test Result']
    _CAM_TESTS = ['cam_stat', 'cam_vc', 'cam_ls', 'cam_mtf']
    _ALS_TESTS = ['als_stat']

    # LED patterns.
    _LED_RUNNING_TEST = ((leds.LED_NUM|leds.LED_CAP, 0.05), (0, 0.05))

    # CSS style classes defined in the corresponding HTML file.
    _STYLE_INFO = "color_idle"
    _STYLE_PASS = "color_good"
    _STYLE_FAIL = "color_bad"

    def t_pass(self, msg):
        return test_ui.MakeLabel(msg, css_class=self._STYLE_PASS)

    def t_fail(self, msg):
        return test_ui.MakeLabel(msg, css_class=self._STYLE_FAIL)

    def update_status(self, mid=None, msg=None):
        message = ''
        if msg:
            message = msg
        elif mid:
            message = test_ui.MakeLabel(self.config['message'][mid + '_en'],
                                        self.config['message'][mid + '_zh'],
                                        self.config['msg_style'][mid])
        self.ui.CallJSFunction("UpdateTestStatus", message)

    def update_pbar(self, pid=None, value=None, add=True):
        precent = 0
        if value:
            percent = value
        elif pid:
            all_time = self.config['chk_point'][self.type]
            if add:
                self.progress += self.config['chk_point'][pid]
            else:
                self.progress = self.config['chk_point'][pid]
            percent = int(round((float(self.progress) / all_time) * 100))
        self.ui.CallJSFunction("UpdatePrograssBar", '%d%%' % percent)

    def register_events(self, events):
        for event in events:
            assert hasattr(self, event)
            self.ui.AddEventHandler(event, getattr(self, event))

    def prepare_test(self):
        self.ref_data = camperf.PrepareTest(self._TEST_CHART_FILE)

    def on_usb_insert(self, dev_path):
        if not self.config_loaded:
            # Initialize common test reference data.
            self.prepare_test()
            # Load config files and reset test results.
            self.dev_path = dev_path
            with MountedMedia(dev_path, 1) as config_dir:
                config_path = os.path.join(config_dir, 'camera.params')
                self.config = self.base_config.Read(config_path)
                self.reset_data()
                self.config_loaded = True
                factory.console.info("Config loaded.")
                self.ui.CallJSFunction("OnUSBInit", self.config['sn_format'])
        else:
            self.dev_path = dev_path
            self.ui.CallJSFunction("OnUSBInsertion")

    def on_usb_remove(self, dev_path):
        if self.config_loaded:
            factory.console.info("USB removal is not allowed during test!")
            self.ui.CallJSFunction("OnUSBRemoval")

    def setup_fixture(self):
        '''Initialize the communication with the fixture.'''
        try:
            self.fixture = Fixture(self.config['fixture'])

            # Go with the default(first) lighting intensity.
            self.light_state = 0
            self.fixture.set_light(self.light_state)
            if not self.unit_test:
                self.fixture.assert_success()
        except Exception as e:
            self.fixture = None
            self.log('Failed to initialize the test fixture.\n')
            return False
        self.log('Test fixture successfully initialized.\n')
        return True

    def sync_fixture(self, event):
        self.ui.CallJSFunction("OnDetectFixtureConnection")
        cnt = 0
        while not self.setup_fixture():
            cnt += 1
            if cnt >= self.config['fixture']['n_retry']:
                self.ui.CallJSFunction("OnRemoveFixtureConnection")
                return
            time.sleep(self.config['fixture']['retry_delay'])
        self.ui.CallJSFunction("OnAddFixtureConnection")

    def on_u2s_insert(self, dev_path):
        if self.config_loaded:
            self.sync_fixture(None)

    def on_u2s_remove(self, dev_path):
        if self.config_loaded:
            self.ui.CallJSFunction("OnRemoveFixtureConnection")

    def update_result(self, row_name, result):
        result_map = {
            True: 'PASSED',
            False: 'FAILED',
            None: 'UNTESTED'
        }
        self.result_dict[row_name] = result_map[result]

    def update_fail_cause(self, fail_cause):
        self.fail_cause = fail_cause

    def reset_data(self):
        self.target = None
        self.target_colorful = None
        self.analyzed = None
        if self.type == _TEST_TYPE_FULL:
            self.log = factory.console.info
        else:
            self.log_to_file = StringIO.StringIO()
            self.log = lambda *x: (factory.console.info(*x),
                                   self.log_to_file.write(*x))

        for var in self.status_names:
            self.update_result(var, None)
        self.fail_cause = ''
        self.progress = 0
        self.ui.CallJSFunction("ResetUiData", "")

    def send_img_to_ui(self, data):
        self.ui.CallJSFunction("ClearBuffer", "")
        # Send the data in 64K packets due to the socket packet size limit.
        data_len = len(data)
        p = 0
        while p < data_len:
            if p + self._PACKET_SIZE > data_len:
                self.ui.CallJSFunction("AddBuffer", data[p:data_len-1])
                p = data_len
            else:
                self.ui.CallJSFunction("AddBuffer",
                                         data[p:p+self._PACKET_SIZE])
                p += self._PACKET_SIZE

    def update_preview(self, img, container_id, scale=0.5):
        # Encode the image in the JPEG format.
        preview = cv2.resize(img, None, fx=scale, fy=scale,
                         interpolation=cv2.INTER_AREA)
        cv2.imwrite('temp.jpg', preview)
        with open('temp.jpg', 'r') as fd:
            img_data = base64.b64encode(fd.read()) + "="

        # Update the preview screen with javascript.
        self.send_img_to_ui(img_data)
        self.ui.CallJSFunction("UpdateImage", container_id)
        return

    def compile_result(self, test_list, use_untest=True):
        ret = self.result_dict
        if all('PASSED' == ret[x] for x in test_list):
            return True
        if use_untest and any('UNTESTED' == ret[x] for x in test_list):
            return None
        return False

    def generate_final_result(self):
        self.update_status(mid='end_test')
        self.cam_pass = self.compile_result(self._CAM_TESTS)
        if self.use_als:
            self.als_pass = self.compile_result(self._ALS_TESTS)
            result = self.compile_result(self.status_names[:-1],
                                         use_untest=False)
        else:
            result = self.compile_result(self._CAM_TESTS, use_untest=False)
        self.update_result('result', result)
        self.log("Result in summary:\n%s\n" %
                 pprint.pformat(self.result_dict))
        Log('cam_performance_test_result', **self.result_dict)
        self.update_pbar(pid='end_test')

    def write_to_usb(self, filename, content, content_type=_CONTENT_TXT):
        try:
            with MountedMedia(self.dev_path, 1) as mount_dir:
                if content_type == _CONTENT_TXT:
                    with open(os.path.join(mount_dir, filename), 'a') as f:
                        f.write(content)
                elif content_type == _CONTENT_IMG:
                    cv2.imwrite(os.path.join(mount_dir, filename), content)
        except:
            self.log("Error when writing data to USB!\n")
            return False
        return True

    def save_log_to_usb(self):
        # Save an image for further analysis in case of the camera
        # performance fail.
        self.update_status(mid='save_to_usb')
        if  (self.target is not None) and (self.log_good_image or
                                           not self.cam_pass):
            if not self.write_to_usb(self.serial_number + ".bmp",
                                     self.target, _CONTENT_IMG):
                return False
            if self.analyzed is not None:
                if not self.write_to_usb(self.serial_number + ".result.jpg",
                                     self.analyzed, _CONTENT_IMG):
                    return False
        return self.write_to_usb(
            self.serial_number + ".txt", self.log_to_file.getvalue())

    def finalize_test(self):
        self.generate_final_result()
        if self.type in [_TEST_TYPE_AB, _TEST_TYPE_MODULE]:
            # We block the test flow until we successfully dumped the result.
            while not self.save_log_to_usb():
                time.sleep(0.5)
            self.update_pbar(pid='save_to_usb')

        # Display final result.
        def get_str(ret, prefix, use_untest=True):
            if ret:
                return self.t_pass(prefix + 'PASS')
            if use_untest and (ret is None):
                return self.t_fail(prefix + 'UNFINISHED')
            return self.t_fail(prefix + 'FAIL')
        cam_result = get_str(self.cam_pass, 'Camera: ', False)
        if self.use_als:
            als_result = get_str(self.als_pass, 'ALS: ')
            self.update_status(msg=cam_result + ' ' + self.fail_cause +
                               '<br>' + als_result)
        else:
            self.update_status(msg=cam_result + ' ' + self.fail_cause)

        # Reset serial number if passed. Otherwise, operator may forget to input
        # serial number again.
        if self.cam_pass and self.type in [_TEST_TYPE_AB, _TEST_TYPE_MODULE]:
            self.ui.CallJSFunction("RestartSnInputBox")

        self.update_pbar(value=100)

    def exit_test(self, event):
        factory.log('%s run_once finished' % self.__class__)
        if self.result_dict['result'] == 'PASSED':
            self.ui.Pass()
        else:
            self.ui.Fail('Camera/ALS test failed.')

    def run_test(self, event=None):
        self.reset_data()
        self.update_status(mid='start_test')

        if self.talk_to_fixture and not self.setup_fixture():
            self.update_status(mid='fixture_fail')
            self.ui.CallJSFunction("OnRemoveFixtureConnection")
            return
        self.update_pbar(pid='start_test')

        if self.auto_serial_number:
            # If fails to get serial number, it will display failed in
            # test_camera_functionality() later
            ret, auto_sn, error_message = self.auto_get_serial_number()
            if ret:
                self.serial_number = auto_sn
                self.log('Read serial number %s\n' % auto_sn)
            else:
                self.serial_number = self._BAD_SERIAL_NUMBER
                self.log('No serial number detected: %s\n' % error_message)
        elif self.type in [_TEST_TYPE_AB, _TEST_TYPE_MODULE]:
            self.serial_number = event.data.get('sn', '')
        else:
            self.serial_number = self._NO_SERIAL_NUMBER

        if self.type == _TEST_TYPE_FULL:
            with leds.Blinker(self._LED_RUNNING_TEST):
                self.test_camera_performance()
                self.update_pbar(pid='cam_finish', add=False)
                if self.use_als:
                    self.test_als_calibration()
                    self.update_pbar(pid='als_finish' + self.type, add=False)
        else:
            self.test_camera_performance()
            self.update_pbar(pid='cam_finish', add=False)
            if self.use_als:
                self.test_als_calibration()
                self.update_pbar(pid='als_finish' + self.type, add=False)

        self.finalize_test()

    def capture_low_noise_image(self, cam, n_samples):
        '''Capture a sequence of images and average them to reduce noise.'''
        if n_samples < 1:
            n_samples = 1
        success, img = cam.read()
        if not success:
            return None
        img = img.astype(np.float64)
        for t in range(n_samples - 1):
            success, temp_img = cam.read()
            if not success:
                return None
            img += temp_img.astype(np.float64)
        img /= n_samples
        return img.round().astype(np.uint8)

    def read_usb_attribute(self, device_string, pattern):
        '''Read and matches regexp pattern in 'lsusb -v' output.

        Args:
          device_string: keyword to search for the camera device
          pattern: regexp pattern with one matching group in MULTILINE mode

        Returns:
          A tuple of (is successful, matched string, error message when failed).
        '''
        lsusb_output = SpawnOutput(['lsusb', '-v'], log=True)

        # Split into several blocks of individual USB device
        splitter = re.compile(r'^Bus\s+\d+\s+Device\s+\d+',
                              flags = re.MULTILINE)
        blocks = splitter.split(lsusb_output)
        matched_blocks = [b for b in blocks if device_string in b]

        err_message = None
        ret = False
        matched_string = None
        if len(matched_blocks) == 0:
            err_message = 'No matched camera device for "%s"' % device_string
        elif len(matched_blocks) > 1:
            err_message = ('Multiple matched devices found for "%s"' %
                           device_string)
        else:
            # Camera module should publish firmware version in 'bcdDevice' field
            search_result = re.search(pattern,
                                      matched_blocks[0], flags = re.MULTILINE)
            if search_result:
                matched_string = search_result.group(1)
                ret = True
            else:
                err_message = (
                    'Regexp "%s" not matched in lsusb output for "%s"' %
                    (pattern, device_string))

        return (ret, matched_string, err_message)

    def verify_firmware(self, device_string, firmware_string):
        '''Checks the firmware version of camera module.

        Args:
          device_string: keyword to search for the camera device
          firmware_string: expected firmware string in bcdDevice field

        Returns:
          A tuple of (is successful, error message when failed).
        '''
        ret, matched_string, err_message = self.read_usb_attribute(
            device_string,
            r'^\s*bcdDevice\s+(\S+)')

        if ret:
            if firmware_string != matched_string:
                err_message = ('Wrong firmware version %s, expecting %s' %
                               (matched_string, firmware_string))
                ret = False

        return (ret, err_message)

    def auto_get_serial_number(self):
        '''Auto read the firmware version of camera module.

        Returns:
          A tuple of (is successful, matched string, error message when failed).
        '''
        if not self.auto_serial_number:
            return (False, None, 'auto_serial_number is not defined')
        ret, matched_string, err_message = self.read_usb_attribute(
            self.auto_serial_number[0],
            self.auto_serial_number[1])
        return (ret, matched_string, err_message)

    def test_camera_functionality(self):
        # Check serial number
        if self.serial_number == self._BAD_SERIAL_NUMBER:
            self.update_result('cam_stat', False)
            self.update_fail_cause("NoCamera")
            return False

        # Check firmware version
        if self.config['firmware']['check_firmware']:
            device_string = self.config['firmware']['device_string']
            firmware_string = self.config['firmware']['firmware_string']
            ret, error_message = self.verify_firmware(device_string,
                                                      firmware_string)
            if not ret:
                self.update_result('cam_stat', False)
                self.update_fail_cause("NoCamera")
                self.log(error_message + '\n')
                return False

        # Initialize the camera with OpenCV.
        self.update_status(mid='init_cam')
        cam = cv2.VideoCapture(self.device_index)
        if not cam.isOpened():
            cam.release()
            self.update_result('cam_stat', False)
            self.update_fail_cause("BadCamera")
            self.log('Failed to initialize the camera. '
                     'Could be bad module, bad connection or '
                     'bad USB initialization.\n')
            return False
        self.update_pbar(pid='init_cam')

        # Set resolution.
        self.update_status(mid='set_cam_res')
        conf = self.config['cam_stat']
        cam.set(cv.CV_CAP_PROP_FRAME_WIDTH, conf['img_width'])
        cam.set(cv.CV_CAP_PROP_FRAME_HEIGHT, conf['img_height'])
        if (conf['img_width'] != cam.get(cv.CV_CAP_PROP_FRAME_WIDTH) or
            conf['img_height'] != cam.get(cv.CV_CAP_PROP_FRAME_HEIGHT)):
            cam.release()
            self.update_result('cam_stat', False)
            self.update_fail_cause("BadCamera")
            self.log("Can't set the image size. "
                     "Possibly caused by bad USB initialization.\n")
            return False
        self.update_pbar(pid='set_cam_res')

        # Try reading an image from the camera.
        self.update_status(mid='try_read_cam')
        success, _ = cam.read()
        if not success:
            cam.release()
            self.update_result('cam_stat', False)
            self.update_fail_cause("BadCamera")
            self.log("Failed to capture an image with the camera.\n")
            return False
        self.update_pbar(pid='try_read_cam')

        # Let the camera's auto-exposure algorithm adjust to the fixture
        # lighting condition.
        self.update_status(mid='wait_cam_awb')
        start = time.time()
        while time.time() - start < conf['buf_time']:
            _, _ = cam.read()
        self.update_pbar(pid='wait_cam_awb')

        # Read the image that we will use.
        self.update_status(mid='record_img')
        n_samples = conf['n_samples']
        self.target_colorful = self.capture_low_noise_image(cam, n_samples)
        if self.target_colorful is None:
            cam.release()
            self.update_result('cam_stat', False)
            self.update_fail_cause("BadCamera")
            self.log("Error reading images from the camera!\n")
            return False
        if self.unit_test:
            self.target_colorful = cv2.imread(self._TEST_SAMPLE_FILE)

        self.target = cv2.cvtColor(self.target_colorful, cv.CV_BGR2GRAY)
        self.update_result('cam_stat', True)
        self.log('Successfully captured a sample image.\n')
        self.update_preview(self.target_colorful, "camera_image",
                            scale=self.config['preview']['scale'])
        cam.release()
        self.update_pbar(pid='record_img')
        return True

    def test_camera_performance(self):
        if not self.test_camera_functionality():
            return

        # Export log to both cros.factory.event_log and text log
        visual_data = {}
        visual_data['camera_sn'] = self.serial_number

        def log_visual_data(value, event_key, log_text_fmt):
            self.log((log_text_fmt % value) + '\n')
            visual_data[event_key] = value

        def finish_log_visual_data():
            Log('cam_performance_visual_analysis', **visual_data)

        # Check the captured test pattern image validity.
        self.update_status(mid='check_vc')

        success, tar_data = camperf.CheckVisualCorrectness(
            self.target, self.ref_data, **self.config['cam_vc'])
        self.analyzed = self.target_colorful.copy()
        renderer.DrawVC(self.analyzed, success, tar_data)
        self.update_preview(self.analyzed, "analyzed_image",
                            scale=self.config['preview']['scale'])

        self.update_result('cam_vc', success)
        if hasattr(tar_data, 'shift'):
            log_visual_data(float(tar_data.shift), 'image_shift',
                            'Image shift percentage: %f')
            log_visual_data(float(tar_data.v_shift[0]), 'image_shift_x',
                            'Image shift X: %f')
            log_visual_data(float(tar_data.v_shift[1]), 'image_shift_y',
                            'Image shift Y: %f')
            log_visual_data(float(tar_data.tilt), 'image_tilt',
                            'Image tilt: %f degrees')
        if not success:
            if hasattr(tar_data, 'sample_corners'):
                log_visual_data(int(tar_data.sample_corners.shape[0]),
                                'corners', 'Found corners count: %d')
            if hasattr(tar_data, 'edges'):
                log_visual_data(int(tar_data.edges.shape[0]), 'edges',
                                'Found square edges count: %d')

            if 'shift' in tar_data.msg:
                self.update_fail_cause('Shift')
            elif 'tilt' in tar_data.msg:
                self.update_fail_cause('Tilt')
            else:
                self.update_fail_cause('WrongImage')

            self.log('Visual correctness: %s\n' % tar_data.msg)
            return
        self.update_pbar(pid='check_vc')

        # Check if the lens shading is present.
        self.update_status(mid='check_ls')
        success, tar_ls = camperf.CheckLensShading(
            self.target, **self.config['cam_ls'])

        self.update_result('cam_ls', success)
        if tar_ls.check_low_freq:
            log_visual_data(float(tar_ls.response), 'ls_low_freq',
                            'Low-frequency response value: %f')
        if tar_ls.lowest_ratio:
            log_visual_data(float(tar_ls.lowest_ratio), 'ls_lowest_ratio',
                            'Len shading ratio: %f')
        if not success:
            self.log('Lens shading: %s\n' % tar_ls.msg)
            self.update_fail_cause('LenShading')
            return
        self.update_pbar(pid='check_ls')

        # Check the image sharpness.
        self.update_status(mid='check_mtf')
        success, tar_mtf = camperf.CheckSharpness(
            self.target, tar_data.edges, **self.config['cam_mtf'])
        renderer.DrawMTF(self.analyzed, tar_data.edges, tar_mtf.perm,
                         tar_mtf.mtfs,
                         self.config['cam_mtf']['mtf_crop_ratio'],
                         self.config['preview']['mtf_color_map_range'])
        self.update_preview(self.analyzed, "analyzed_image",
                            scale=self.config['preview']['scale'])

        self.update_result('cam_mtf', success)
        log_visual_data(float(tar_mtf.mtf), 'median_MTF', 'MTF value: %f')
        if hasattr(tar_mtf, 'min_mtf'):
            log_visual_data(float(tar_mtf.min_mtf), 'lowest_MTF',
                            'Lowest MTF value: %f')
        if not success:
            self.log('Sharpness: %s\n' % tar_mtf.msg)
            self.update_fail_cause('MTF')

        finish_log_visual_data()
        self.update_pbar(pid='check_mtf')
        return

    def test_als_write_vpd(self, calib_result):
        self.update_status(mid='dump_to_vpd')
        conf = self.config['als']
        if not calib_result:
            self.update_result('als_stat', False)
            self.update_fail_cause("ALS")
            self.log('ALS calibration data is incorrect.\n')
            return False
        if subprocess.call(conf['save_vpd'] % calib_result, shell=True):
            self.update_result('als_stat', False)
            self.update_fail_cause("ALS")
            self.log('Writing VPD data failed!\n')
            return False
        self.log('Successfully calibrated ALS scales.\n')
        self.update_pbar(pid='dump_to_vpd')
        return True

    def test_als_switch_to_next_light(self):
        self.update_status(mid='adjust_light')
        conf = self.config['als']
        self.light_state += 1
        self.fixture.set_light(self.light_state)
        self.update_pbar(pid='adjust_light')
        if not self.unit_test:
            self.fixture.assert_success()
        if self.light_state >= len(conf['luxs']):
            return False
        self.update_status(mid='wait_fixture')
        self.fixture.wait_for_light_switch()
        self.update_pbar(pid='wait_fixture')
        return True

    def test_als_calibration(self):
        # Initialize the ALS.
        self.update_status(mid='init_als')
        conf = self.config['als']
        self.als = ALS(val_path=conf['val_path'],
                       scale_path=conf['scale_path'])
        if not self.als.detected:
            self.update_result('als_stat', False)
            self.update_fail_cause("ALS")
            self.log('Failed to initialize the ALS.\n')
            return
        self.als.set_scale_factor(conf['calibscale'])
        self.update_pbar(pid='init_als')

        # Go through all different lighting settings
        # and record ALS values.
        calib_result = 0
        try:
            vals = []
            while True:
                # Get ALS values.
                self.update_status(mid='read_als%d' % self.light_state)
                scale = self.als.get_scale_factor()
                val = self.als.read_mean(samples=conf['n_samples'],
                                         delay=conf['read_delay'])
                vals.append(val)
                self.log('Lighting preset lux value: %d\n' %
                         conf['luxs'][self.light_state])
                self.log('ALS value: %d\n' % val)
                self.log('ALS calibration scale: %d\n' % scale)
                # Check if it is a false read.
                if not val:
                    self.update_result('als_stat', False)
                    self.update_fail_cause("ALS")
                    self.log('The ALS value is stuck at zero.\n')
                    return
                # Compute calibration data if it is the calibration target.
                if conf['luxs'][self.light_state] == conf['calib_lux']:
                    calib_result = int(round(float(conf['calib_target']) /
                                             val * scale))
                    self.log('ALS calibration data will be %d\n' %
                             calib_result)
                self.update_pbar(pid='read_als%d' % self.light_state)

                # Go to the next lighting preset.
                if not self.test_als_switch_to_next_light():
                    break

            # Check value ordering.
            for i, li in enumerate(conf['luxs']):
                for j in range(i):
                    if ((li > conf['luxs'][j] and vals[j] >= vals[i]) or
                        (li < conf['luxs'][j] and vals[j] <= vals[i])):
                        self.update_result('als_stat', False)
                        self.update_fail_cause("ALS")
                        self.log('The ordering of ALS values is wrong.\n')
                        return
        except (FixtureException, serial.serialutil.SerialException) as e:
            self.fixture = None
            self.update_result('als_stat', None)
            self.log("The test fixture was disconnected!\n")
            self.ui.CallJSFunction("OnRemoveFixtureConnection")
            return
        except:
            self.update_result('als_stat', False)
            self.update_fail_cause("ALS")
            self.log('Failed to read values from ALS or unknown error.\n')
            return
        self.log('Successfully recorded ALS values.\n')

        # Save ALS values to vpd for FATP test.
        if self.type == _TEST_TYPE_FULL:
            if not self.test_als_write_vpd(calib_result):
                return
        self.update_result('als_stat', True)
        return

    def run_once(self, test_type = _TEST_TYPE_FULL, unit_test = False,
                 use_als = True, log_good_image = False,
                 device_index = -1, ignore_enter_key = False,
                 auto_serial_number = None):
        '''The entry point of the test.

        Args:
            test_type: Run the full machine test or the AB panel test. The AB
                       panel will be run on a host that is used to test
                       connected AB panels (possibly many), while the full
                       machine test would test only the machine that runs it
                       and then exit.
            unit_test: Run the unit-test mode. The unit-test mode is used to
                       test the test integrity when the test fixture is not
                       available. It should be run on a machine that has a
                       working camera and a working ALS. Please place the
                       camera parameter file under the src directory on an USB
                       stick for use and connect the machine with an
                       USB-to-RS232 converter cable with the designated chipset
                       in the parameter file. The test will replace the
                       captured image with the sample test image and run the
                       camera performance test on it.
            use_als:    Whether to use the ambient light sensor.
            log_good_image: Log images that pass that test
                            (By default, only failed images are logged)
            device_index: video device index (-1 to auto pick device by OpenCV)
            ignore_enter_key: disable enter key in serial number input
                              (Some barcode reader automatically input enter
                               key, but we may prefer not to start the test
                               immediately after barcode is scanned)
            auto_serial_number: None or (module keyword, regexp pattern with one
                                matching group in MULTILINE mode)
                                It support all Module, AB, and Full test types.
                                Ex: ('VendorName', r'^\s*iSerial\s+\S+\s+(\S+)')
        '''
        factory.log('%s run_once' % self.__class__)

        # Add signal handler to close opened camera interface when get killed
        # TODO: this should be done in autotest framework instead
        signal_handler = lambda signum, frame: sys.exit(1)
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        # Initialize variables and environment.
        assert test_type in [_TEST_TYPE_FULL, _TEST_TYPE_AB, _TEST_TYPE_MODULE]
        assert unit_test in [True, False]
        assert use_als in [True, False]
        assert log_good_image in [True, False]
        assert ignore_enter_key in [True, False]
        assert auto_serial_number is None or type(auto_serial_number) == tuple
        self.type = test_type
        self.unit_test = unit_test
        self.use_als = use_als
        self.log_good_image = log_good_image
        self.device_index = device_index
        self.ignore_enter_key = ignore_enter_key
        self.auto_serial_number = auto_serial_number

        self.talk_to_fixture = use_als
        self.config_loaded = False
        self.status_names = self._STATUS_NAMES
        self.status_labels = self._STATUS_LABELS
        self.result_dict = {}
        self.fail_cause = ''
        self.base_config = PluggableConfig({})
        os.chdir(self.srcdir)

        # Setup the usb disk and usb-to-serial adapter monitor.
        usb_monitor = ConnectionMonitor()
        usb_monitor.start(subsystem='block', device_type='disk',
                          on_insert=self.on_usb_insert,
                          on_remove=self.on_usb_remove)

        if self.talk_to_fixture:
            u2s_monitor = ConnectionMonitor()
            u2s_monitor.start(subsystem='usb-serial',
                              on_insert=self.on_u2s_insert,
                              on_remove=self.on_u2s_remove)

        if self.type == _TEST_TYPE_FULL or self.auto_serial_number:
            input_serial_number = False
        else:
            input_serial_number = True

        # Startup the UI.
        self.ui = UI()
        self.register_events(['sync_fixture', 'exit_test', 'run_test'])
        self.ui.CallJSFunction("InitLayout", self.talk_to_fixture,
                               input_serial_number,
                               self.ignore_enter_key)
        self.ui.Run()
