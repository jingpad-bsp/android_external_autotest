# -*- coding: utf-8 -*-
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(sheckylin): Refactor the code with the new HTML5 framework.

# Import guard for OpenCV.
try:
    import cv
    import cv2
except ImportError:
    pass

import gtk
import logging
import numpy as np
import os
import pprint
import re
import serial
import StringIO
import time

import autotest_lib.client.cros.camera.perf_tester as camperf

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory_setup_modules
from cros.factory.test import factory
from cros.factory.test import ui as ful
from cros.factory.test import leds
from cros.factory.test.media_util import MediaMonitor
from cros.factory.test.media_util import MountedMedia
from autotest_lib.client.cros.rf.config import PluggableConfig
from autotest_lib.client.cros import tty

_MESSAGE_USB = (
    'Please insert the usb stick to load parameters.\n'
    '請插入usb以讀取測試參數\n')
_MESSAGE_PREPARE_MACHINE = (
    'Please put the machine in the fixture and connect the keyboard.\n'
    'Then press ENTER.\n'
    '請將待測機器放入盒中並連接鍵盤\n'
    '備妥後按ENTER\n')
_MESSAGE_PREPARE_PANEL = (
    'Please connect the next AB panel.\n'
    'Then press ENTER to scan the barcode.\n'
    '請連接下一塊AB Panel\n'
    '備妥後按ENTER掃描序號\n')
_MESSAGE_PREPARE_CAMERA = (
    'Make sure the camera is connected\n'
    'Then press ENTER to proceed, TAB to skip.\n'
    '確定 攝像頭 連接完成\n'
    '備妥後按ENTER繼續, 或按TAB跳過\n')
_MESSAGE_PREPARE_ALS = (
    'Make sure the light sensor is connected\n'
    'Then press ENTER to proceed, TAB to skip.\n'
    '確定 光感測器 連接完成\n'
    '備妥後按ENTER繼續, 或按TAB跳過\n')
_MESSAGE_RESULT_TAB_ABONLY = (
    'Results are listed below.\n'
    'Please disconnect the panel and press ENTER to write log.\n'
    '測試結果顯示如下\n'
    '請將AB Panel移除, 並按ENTER寫入測試結果\n')
_MESSAGE_RESULT_TAB_FULL = (
    'Results are listed below.\n'
    'Please disconnect the machine and press ENTER to write log.\n'
    '測試結果顯示如下\n'
    '請將測試機器移除, 並按ENTER寫入測試結果\n')

_TEST_SN_NUMBER = 'TEST-SN-NUMBER'
_LABEL_SIZE = (300, 30)

# Test type constants:
_TEST_TYPE_AB = 'AB'
_TEST_TYPE_FULL = 'Full'

# Content type constants:
_CONTENT_IMG = 'image'
_CONTENT_TXT = 'text'

def make_prepare_widget(message, on_key_enter, on_key_tab=None):
    """Returns a widget that display the message and bind proper functions."""
    widget = gtk.VBox()
    widget.add(ful.make_label(message))
    def key_release_callback(widget, event):
        if event.keyval == gtk.keysyms.Tab:
            if on_key_tab is not None:
                return on_key_tab()
        elif event.keyval == gtk.keysyms.Return:
            return on_key_enter()
    widget.key_callback = key_release_callback
    return widget


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
        for dummy in range(samples):
            fd = open(self.val_path)
            buf.append(int(fd.readline().rstrip()))
            fd.close()
            time.sleep(delay)

        return buf

    def read_mean(self, delay=None, samples=1):
        if not self.detected:
            return None

        buf = self._read(delay, samples)
        return sum(buf) / len(buf)

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


class factory_CameraPerformanceAls(test.test):
    version = 1
    preserve_srcdir = True

    # OpenCV will automatically search for a working camera device if we use
    # the index -1.
    _DEVICE_INDEX = -1
    _TEST_CHART_FILE = 'test_chart.png'
    _TEST_SAMPLE_FILE = 'sample.png'

    # States for the state machine.
    _STATE_INITIAL = -1
    _STATE_WAIT_USB = 0
    _STATE_PREPARE_MACHINE = 1
    _STATE_ENTERING_SN = 2
    _STATE_PREPARE_CAMERA = 3
    _STATE_PREPARE_ALS = 4
    _STATE_RESULT_TAB = 5

    # Status in the final result tab.
    _STATUS_NAMES = ['sn', 'cam_stat', 'cam_vc', 'cam_ls', 'cam_mtf',
                     'als_stat', 'result']
    _STATUS_LABELS = ['Serial Number',
                      'Camera Functionality',
                      'Camera Visual Correctness',
                      'Camera Lens Shading',
                      'Camera Image Sharpness',
                      'ALS Functionality',
                      'Test Result']

    # LED patterns.
    _LED_PREPARE_CAM_TEST = ((leds.LED_NUM, 0.25), (0, 0.25))
    _LED_RUNNING_CAM_TEST = ((leds.LED_NUM, 0.05), (0, 0.05))
    _LED_PREPARE_ALS_TEST = ((leds.LED_NUM|leds.LED_CAP, 0.25),
                             (leds.LED_NUM, 0.25))
    _LED_RUNNING_ALS_TEST = ((leds.LED_NUM|leds.LED_CAP, 0.05),
                             (leds.LED_NUM, 0.05))
    _LED_FINISHED_ALL_TEST = ((leds.LED_NUM|leds.LED_CAP, 0.25),
                              (leds.LED_NUM|leds.LED_CAP, 0.25))

    def advance_state(self):
        if self.type == _TEST_TYPE_FULL:
            self._state = self._state + 1
            # Skip entering SN for full machine test.
            if self._state == self._STATE_ENTERING_SN:
                self._state = self._state + 1
        else:
            if self._state == self._STATE_RESULT_TAB:
                self._state = self._STATE_PREPARE_MACHINE
            else:
                self._state = self._state + 1
        self.switch_widget(self._state_widget[self._state])

    def prepare_test(self):
        self.ref_data = camperf.PrepareTest(self._TEST_CHART_FILE)

    def on_usb_insert(self, dev_path):
        if self._state == self._STATE_WAIT_USB:
            # Initialize common test reference data.
            self.prepare_test()
            # Load config files and reset test results.
            self.dev_path = dev_path
            with MountedMedia(dev_path, 1) as config_dir:
                config_path = os.path.join(config_dir, 'camera.params')
                self.config = self.base_config.Read(config_path)
                self.reset_data()
                self.advance_state()
                factory.log("Config loaded.")

    def on_usb_remove(self, dev_path):
        if self._state != self._STATE_WAIT_USB:
            raise Exception("USB removal is not allowed during test")

    def register_callbacks(self, window):
        def key_press_callback(widget, event):
            if hasattr(self, 'last_widget'):
                if hasattr(self.last_widget, 'key_callback'):
                    return self.last_widget.key_callback(widget, event)
            return False
        window.connect('key-press-event', key_press_callback)
        window.add_events(gtk.gdk.KEY_PRESS_MASK)

    def switch_widget(self, widget_to_display):
        if hasattr(self, 'last_widget'):
            if widget_to_display is not self.last_widget:
                self.last_widget.hide()
                self.test_widget.remove(self.last_widget)
            else:
                return

        self.last_widget = widget_to_display
        self.test_widget.add(widget_to_display)
        self.test_widget.show_all()

    def on_sn_keypress(self, entry, key):
        if key.keyval == gtk.keysyms.Tab:
            entry.set_text(_TEST_SN_NUMBER)
            return True
        return False

    def on_sn_complete(self, serial_number):
        self.serial_number = serial_number
        # TODO(itspeter): display the SN info in the result tab.
        self._update_status('sn', self.check_sn_format(serial_number))
        self.advance_state()

    def check_sn_format(self, sn):
        if re.search(self.config['sn_format'], sn):
            return True
        return False

    def write_to_usb(self, filename, content, content_type=_CONTENT_TXT):
        with MountedMedia(self.dev_path, 1) as mount_dir:
            if content_type == _CONTENT_TXT:
                with open(os.path.join(mount_dir, filename), 'w') as f:
                    f.write(content)
            elif content_type == _CONTENT_IMG:
                cv2.imwrite(os.path.join(mount_dir, filename), content)
        return True

    def _setup_fixture(self):
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

    def _capture_low_noise_image(self, cam, n_samples):
        '''Capture a sequence of images and average them to reduce noise.'''
        if n_samples < 1:
            n_samples = 1
        _, img = cam.read()
        img = img.astype(np.float64)
        for t in range(n_samples - 1):
            _, temp_img = cam.read()
            img += temp_img.astype(np.float64)
        img /= n_samples
        return img.round().astype(np.uint8)

    def _test_camera_functionality(self):
        # Initialize the camera with OpenCV.
        cam = cv2.VideoCapture(self._DEVICE_INDEX)
        if not cam.isOpened():
            cam.release()
            self._update_status('cam_stat', False)
            self.log('Failed to initialize the camera. '
                     'Could be bad module, bad connection or '
                     'insufficient USB bandwidth.\n')
            return False

        # Set resolution.
        conf = self.config['cam_stat']
        cam.set(cv.CV_CAP_PROP_FRAME_WIDTH, conf['img_width'])
        cam.set(cv.CV_CAP_PROP_FRAME_HEIGHT, conf['img_height'])
        if (conf['img_width'] != cam.get(cv.CV_CAP_PROP_FRAME_WIDTH) or
            conf['img_height'] != cam.get(cv.CV_CAP_PROP_FRAME_HEIGHT)):
            cam.release()
            self._update_status('cam_stat', False)
            self.log("Can't set the image size. "
                     "Possibly caused by insufficient USB bandwidth.\n")
            return False

        # Try reading an image from the camera.
        success, _ = cam.read()
        if not success:
            cam.release()
            self._update_status('cam_stat', False)
            self.log("Failed to capture an image with the camera.\n")
            return False

        # Let the camera's auto-exposure algorithm adjust to the fixture
        # lighting condition.
        start = time.clock()
        while time.clock() - start < conf['buf_time']:
            _, _ = cam.read()

        # Read the image that we will use.
        n_samples = conf['n_samples']
        img = self._capture_low_noise_image(cam, n_samples)
        self.target = cv2.cvtColor(img, cv.CV_BGR2GRAY)
        self._update_status('cam_stat', True)
        self.log('Successfully captured an image.\n')

        # Use the sample image in the unit-test mode.
        if self.unit_test:
            self.target = cv2.imread(self._TEST_SAMPLE_FILE,
                                     cv.CV_LOAD_IMAGE_GRAYSCALE)
        cam.release()
        return True

    def _test_camera_core(self):
        if not self._test_camera_functionality():
            return

        # Check the captured test pattern image validity.
        success, tar_data = camperf.CheckVisualCorrectness(
            self.target, self.ref_data, **self.config['cam_vc'])

        self._update_status('cam_vc', success)
        if hasattr(tar_data, 'shift'):
            self.log('Image shift percentage: %f\n' % tar_data.shift)
            self.log('Image tilt: %f degrees\n' % tar_data.tilt)
        if not success:
            if hasattr(tar_data, 'sample_corners'):
                self.log('Found corners count: %d\n' %
                         tar_data.sample_corners.shape[0])
            if hasattr(tar_data, 'edges'):
                self.log('Found square edges count: %d\n' %
                         tar_data.edges.shape[0])
            self.log('Visual correctness: %s\n' % tar_data.msg)
            return

        # Check if the lens shading is present.
        success, tar_ls = camperf.CheckLensShading(
            self.target, **self.config['cam_ls'])

        self._update_status('cam_ls', success)
        if tar_ls.check_low_freq:
            self.log('Low-frequency response value: %f\n' %
                                   tar_ls.response)
        if not success:
            self.log('Lens shading: %s\n' % tar_ls.msg)
            return

        # Check the image sharpness.
        success, tar_mtf = camperf.CheckSharpness(
            self.target, tar_data.edges, **self.config['cam_mtf'])

        self._update_status('cam_mtf', success)
        self.log('MTF value: %f\n' % tar_mtf.mtf)
        if hasattr(tar_mtf, 'min_mtf'):
            self.log('Lowest MTF value: %f\n' % tar_mtf.min_mtf)
        if not success:
            self.log('Sharpness: %s\n' % tar_mtf.msg)
        return

    def _test_als_core(self):
        # Initialize the ALS.
        conf = self.config['als']
        self.als = ALS(val_path=conf['val_path'],
                       scale_path=conf['scale_path'])
        if not self.als.detected:
            self._update_status('als_stat', False)
            self.log('Failed to initialize the ALS.\n')
            return

        # Go through all different lighting settings
        # and record ALS values.
        try:
            while True:
                # Get ALS values.
                scale = self.als.get_scale_factor()
                val = self.als.read_mean(samples=5, delay=0)
                self.log('Lighting preset lux value: %d\n' %
                         conf['luxs'][self.light_state])
                self.log('ALS value: %d\n' % val)
                self.log('ALS calibration scale: %d\n' % scale)

                # Go to the next lighting preset.
                self.light_state += 1
                self.fixture.set_light(self.light_state)
                if not self.unit_test:
                    self.fixture.assert_success()
                if self.light_state >= len(conf['luxs']):
                    break
                self.fixture.wait_for_light_switch()
        except (FixtureException, serial.serialutil.SerialException) as e:
            self.fixture = None
            self._update_status('als_stat', None)
            self.log("The test fixture was disconnected!\n")
            return
        except:
            self._update_status('als_stat', False)
            self.log('Failed to read values from ALS.\n')
            return
        self._update_status('als_stat', True)
        self.log('Successfully recorded ALS values.\n')
        return

    def test_camera(self, skip_flag):
        if self.type == _TEST_TYPE_FULL:
            self.blinker.Stop()

            if not skip_flag:
                with leds.Blinker(self._LED_RUNNING_CAM_TEST):
                    self._test_camera_core()

            self.blinker = leds.Blinker(self._LED_PREPARE_ALS_TEST)
            self.blinker.Start()
        else:
            if not skip_flag:
                self._test_camera_core()

        self.advance_state()

    def test_als(self, skip_flag):
        if self.type == _TEST_TYPE_FULL:
            self.blinker.Stop()

            if not skip_flag:
                with leds.Blinker(self._LED_RUNNING_ALS_TEST):
                    self._test_als_core()

            self.blinker = leds.Blinker(self._LED_FINISHED_ALL_TEST)
            self.blinker.Start()
        else:
            if not skip_flag:
                self._test_als_core()

        self.generate_final_result()
        self.advance_state()

    def _update_status(self, row_name, result):
        """Updates status in display_dict."""
        result_map = {
            True: ful.PASSED,
            False: ful.FAILED,
            None: ful.UNTESTED
        }
        assert result in result_map, "Unknown result"
        self.display_dict[row_name]['status'] = result_map[result]

    def generate_final_result(self):
        self._result = all(
           ful.PASSED == self.display_dict[var]['status']
           for var in self.status_names[:-1])
        self._update_status('result', self._result)
        self.log("Result in summary:\n%s\n" %
                 pprint.pformat(self.display_dict))

    def save_log(self):
        # Save an image for further analysis in case of the camera
        # performance fail.
        cam_perf_pass = all(ful.PASSED == self.display_dict[var]['status']
                            for var in ['cam_vc', 'cam_ls', 'cam_mtf'])
        if (not cam_perf_pass) and (self.target is not None):
            if not self.write_to_usb(self.serial_number + ".bmp",
                                     self.target, _CONTENT_IMG):
                return False
        return self.write_to_usb(
            self.serial_number + ".txt", self.log_to_file.getvalue())

    def reset_data(self):
        self.target = None
        if self.type == _TEST_TYPE_FULL:
            self.log = logging.info
        else:
            self.log_to_file = StringIO.StringIO()
            self.sn_input_widget.get_entry().set_text('')
            self.log = self.log_to_file.write

        for var in self.status_names:
            self._update_status(var, None)

    def on_result_enter(self):
        if self.type == _TEST_TYPE_FULL:
            self.blinker.Stop()
            gtk.main_quit()
        else:
            # The UI will stop in this screen unless log is saved.
            if self.save_log():
                self.reset_data()
                self.advance_state()
        return False

    def on_close_prepare_machine(self):
        if self.type == _TEST_TYPE_FULL:
            self.blinker = leds.Blinker(self._LED_PREPARE_CAM_TEST)
            self.blinker.Start()
        # Try to setup the fixture. This step blocks until we can find the
        # fixture successfully.
        if not self._setup_fixture():
            return False
        self.advance_state()
        return True

    def make_result_widget(self, on_key_enter):
        widget = gtk.VBox()
        widget.add(ful.make_label(_MESSAGE_RESULT_TAB_FULL
                                  if self.type == _TEST_TYPE_FULL
                                  else _MESSAGE_RESULT_TAB_ABONLY))

        for name, label in zip(self.status_names, self.status_labels):
            td, tw = ful.make_status_row(label, ful.UNTESTED, _LABEL_SIZE)
            self.display_dict[name] = td
            widget.add(tw)
        def key_press_callback(widget, event):
            if event.keyval == gtk.keysyms.Return:
                on_key_enter()

        widget.key_callback = key_press_callback
        return widget

    def run_once(self, test_type=_TEST_TYPE_FULL, unit_test=False):
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
        '''
        factory.log('%s run_once' % self.__class__)

        # Initialize variables.
        assert test_type in [_TEST_TYPE_FULL, _TEST_TYPE_AB]
        assert unit_test in [True, False]
        self.type = test_type
        self.unit_test = unit_test
        self.display_dict = {}
        self.base_config = PluggableConfig({})
        self.last_handler = None
        os.chdir(self.srcdir)
        if self.type == _TEST_TYPE_FULL:
            self.status_names = self._STATUS_NAMES[1:]
            self.status_labels = self._STATUS_LABELS[1:]
        else:
            self.status_names = self._STATUS_NAMES
            self.status_labels = self._STATUS_LABELS

        # Set up the UI widgets.
        self.usb_prompt_widget = gtk.VBox()
        self.usb_prompt_widget.add(ful.make_label(_MESSAGE_USB))
        self.prepare_machine_widget = make_prepare_widget(
            (_MESSAGE_PREPARE_MACHINE if self.type == _TEST_TYPE_FULL
             else _MESSAGE_PREPARE_PANEL),
            self.on_close_prepare_machine)
        self.prepare_camera_widget = make_prepare_widget(
                _MESSAGE_PREPARE_CAMERA,
                lambda : self.test_camera(skip_flag=False),
                lambda : self.test_camera(skip_flag=True))
        self.prepare_als_widget = make_prepare_widget(
                _MESSAGE_PREPARE_ALS,
                lambda : self.test_als(skip_flag=False),
                lambda : self.test_als(skip_flag=True))
        self.result_widget = self.make_result_widget(self.on_result_enter)

        self.sn_input_widget = ful.make_input_window(
            prompt='Enter Serial Number (TAB to use testing sample SN):',
            on_validate=self.check_sn_format,
            on_keypress=self.on_sn_keypress,
            on_complete=self.on_sn_complete)

        # Make sure the entry in widget will have focus.
        self.sn_input_widget.connect(
            "show",
            lambda *x : self.sn_input_widget.get_entry().grab_focus())

        # Setup the relation of states and widgets.
        self._state_widget = {
            self._STATE_INITIAL: None,
            self._STATE_WAIT_USB: self.usb_prompt_widget,
            self._STATE_PREPARE_MACHINE: self.prepare_machine_widget,
            self._STATE_ENTERING_SN: self.sn_input_widget,
            self._STATE_PREPARE_CAMERA: self.prepare_camera_widget,
            self._STATE_PREPARE_ALS: self.prepare_als_widget,
            self._STATE_RESULT_TAB: self.result_widget
        }

        # Setup the usb monitor,
        monitor = MediaMonitor()
        monitor.start(on_insert=self.on_usb_insert,
                      on_remove=self.on_usb_remove)

        # Setup the initial display.
        self.test_widget = gtk.VBox()
        self._state = self._STATE_INITIAL
        self.advance_state()
        ful.run_test_widget(
                self.job,
                self.test_widget,
                window_registration_callback=self.register_callbacks)

        if not self._result:
            raise error.TestFail('Camera/ALS test failed by user indication\n' +
                                 '品管人員懷疑故障，請檢修')

        factory.log('%s run_once finished' % self.__class__)
