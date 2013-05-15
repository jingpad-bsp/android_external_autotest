# -*- coding: utf-8 -*-
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import gtk
import os
import pprint
import re
import tempfile
import time
import StringIO
import subprocess

from autotest_lib.client.cros import factory_setup_modules
from cros.factory.event_log import EventLog
from cros.factory.test import factory
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.audio import audio_helper
from autotest_lib.client.cros.camera.camera_preview import CameraPreview
from cros.factory.test import state_machine
from cros.factory.test.media_util import MediaMonitor
from cros.factory.test.media_util import MountedMedia
from autotest_lib.client.cros.i2c import usb_to_i2c
from autotest_lib.client.cros.rf.config import PluggableConfig
from autotest_lib.client.common_lib import utils

_MESSAGE_USB = (
    'Please insert the usb stick, adapter board and golden reference.\n'
    '请插入USB随身碟, 测试板, 良品 以读取测试参数\n')
_MESSAGE_PREPARE_PANEL = (
    'Please prepare the next AB panel.\n'
    'Be sure all the connector is connected.\n'
    'Press ENTER to execute connectivity test.\n'
    '请连接下一块AB Panel\n'
    '备妥后按ENTER执行测试\n')
_MESSAGE_ENTER_SN_HINT = ('Please scan SN on LCD.\n请扫描本体上S/N:')
_MESSAGE_CAMERA_CHECK = (
    'hit TAB to pass and ENTER to fail.\n' +
    '成功请按 TAB, 错误请按 ENTER.\n')
_MESSAGE_PROBING = (
    'Probing components...\n'
    '测试中...\n')
_MESSAGE_PLAYING_AUDIO = (
    'Testing DMIC...\n'
    '测试麦克风中...请保持安静\n')
_MESSAGE_DISPLAY = (
    'Hit TAB if DUT have something displayed.\n' +
    'Otherwise, hit ENTER.\n' +
    '成功在测试品看到画面请按 TAB, 否则请按 ENTER.\n')
_MESSAGE_WRITING_LOGS = (
    'Writing logs...\n'
    '纪录中...\n')
_MESSAGE_RESULT_TAB = (
    'Results are listed below.\n'
    'Remove the panel after all power is turned off..\n'
    '测试结果显示如下\n'
    '确认电源皆断电后, 将Panel移除\n')

_TEST_SN_NUMBER = 'TEST-SN-NUMBER'
COLOR_MAGENTA = gtk.gdk.color_parse('magenta1')
BRIGHTNESS_CONTROL_CMD = (
    'echo %s > /sys/class/backlight/intel_backlight/brightness')

# Regular expressions to match audiofuntest message.
_AUDIOFUNTEST_STOP_RE = re.compile('^Stop')
_AUDIOFUNTEST_SUCCESS_RATE_RE = re.compile('.*rate\s=\s(.*)$')


class factory_Connector(state_machine.FactoryStateMachine):
    version = 8

    def setup_tests(self):
        # Register more states for test procedure with configuration data
        # loaded from external media device (USB/SD).

        # Execute board specific commands
        if 'board_specific' in self.config:
            self.run_cmds(self.config['board_specific'])

        self.fixture_config = self.config.get('fixture_control', None)

        # Setup serial number input widget.
        self.sn_input_widget = self.make_serial_number_widget(
            message=_MESSAGE_ENTER_SN_HINT,
            default_validate_regex=self.config['sn_regex'],
            on_complete=self.on_sn_complete,
            on_keypress=self.on_sn_keypress,
            generate_status_row=True)
        self.register_state(self.sn_input_widget)

        if 'display' in self.config:
            self.setup_display_test()
            self.register_state(
                self.display_widget, None, self.perform_display_test)

        if 'camera' in self.config:
            self.setup_camera_preview()
            self.register_state(self.preview_widget, None,
                                self.perform_camera_preview)

        if 'probing' in self.config:
            self.setup_probing()
            self.probing_widget = self.make_decision_widget(
                message=_MESSAGE_PROBING, key_action_mapping={})
            self.register_state(self.probing_widget, None,
                                self.perform_probing)

        if 'audio' in self.config:
            self.setup_audio()
            self.audio_widget = self.make_decision_widget(
                message=_MESSAGE_PLAYING_AUDIO, key_action_mapping={})
            self.register_state(self.audio_widget, None,
                                self.perform_audio)

        self.writing_widget = self.make_decision_widget(
            message=_MESSAGE_WRITING_LOGS,
            key_action_mapping={},
            fg_color=COLOR_MAGENTA)
        self.register_state(self.writing_widget, None, self.write_log)

        # Setup result tab.
        self.result_widget = self.make_result_widget(
            _MESSAGE_RESULT_TAB,
            key_action_mapping={
                gtk.keysyms.Return: (self.advance_state, [])})
        # After this state (result), go back to "prepare panel" state.
        self.register_state(self.result_widget, None, None,
                            self._STATE_PREPARE_PANEL)

        # Execute commands for special SKU.
        if 'pre_setup' in self.config:
            for cmd_tuple in self.config['pre_setup']:
                cmd, expect_re = cmd_tuple
                self.run_cmd(cmd, expect_re)

    def setup_camera_preview(self):
        self.camera_config = self.config['camera']
        factory.log('Camera config is [%s]' % self.camera_config)
        # Prepare the status row.
        self._status_rows.append(('camera', 'Camera Preview', True))
        self._results_to_check.append('camera')
        # Setup preview widget
        self.camera_preview = CameraPreview(
            key_action_mapping={
                gtk.keysyms.Tab: self.pass_preview_test,
                gtk.keysyms.Return: self.fail_preview_test},
            msg=_MESSAGE_CAMERA_CHECK,
            device_index=int(self.camera_config['DEVICE_INDEX']),
            width=int(self.camera_config['WIDTH']),
            height=int(self.camera_config['HEIGHT']))
        self.preview_widget = self.camera_preview.widget

    def pass_preview_test(self):
        self.camera_preview.capture_stop()
        factory.log('Preview passed.')
        self.update_status('camera', True)
        self.advance_state()

    def fail_preview_test(self):
        self.camera_preview.capture_stop()
        factory.log('Preview failed.')
        self.update_status('camera', False)
        self.advance_state()

    def perform_camera_preview(self):
        try:
            if self.camera_config['IS_AUTO']:
                self.camera_preview.init_device(start_capture=False)
                ret, cvImg = self.camera_preview.capture_single()
                self.pass_preview_test()
            else:
                self.camera_preview.init_device()
        except IOError as e:
            factory.log('Cannot get cammera - %s' % e)
            self.fail_preview_test()

    def setup_probing(self):
        self.probing_config = self.config['probing']
        factory.log('Probing config is [%s]' % self.probing_config)
        if self.is_internal:
            self.setup_internal_probing()
        else:
            self.setup_external_probing()

    def setup_internal_probing(self):
        # Prepare the status row.
        self.probe_list = self.probing_config['items']
        for test_name in sorted(self.probe_list.iterkeys()):
            self._status_rows.append((test_name, test_name, True))
            self._results_to_check.append(test_name)

    def setup_external_probing(self):
        self.probe_list = self.probing_config['i2c_list']
        self.chipset = self.probing_config['chipset']
        # Prepare the status row.
        for test_name, test_label, _ in self.probe_list:
            self._status_rows.append((test_name, test_label, True))
            self._results_to_check.append(test_name)

    def setup_audio(self):
        self.audio_config = self.config['audio']
        factory.log('Audio config is [%s]' % self.audio_config)
        self.play_freq = self.audio_config['freq']
        self.play_repeat = self.audio_config['repeat']
        self.play_tolerance = self.audio_config['tolerance']
        self.play_duration = self.audio_config['duration']
        self.use_audiofuntest = self.audio_config['audiofuntest']
        # Prepare the status row.
        self._status_rows.append(('audio', 'Audio', False))
        self._results_to_check.append('audio')

    def perform_probing(self):
        if self.is_internal:
            self.perform_internal_probing()
        else:
            self.perform_external_probing()
        self.advance_state()

    def perform_internal_probing(self):
        for test_name in sorted(self.probe_list.iterkeys()):
            commands = self.probe_list[test_name]
            self.update_status(test_name, True)
            for cmd, expect_re in commands:
                if not self.run_cmd(cmd, expect_re):
                    self.update_status(test_name, False)

    def perform_external_probing(self):
        try:
            controller = usb_to_i2c.create_i2c_controller(self.chipset)
            # Turn on the led light to indicate test in progress.
            # http://www.nxp.com/documents/data_sheet/SC18IM700.pdf
            controller.send_and_check_status(
                98, [0x11, 0x97, 0x80, 0x00, 0x40, 0xE1])
            # Probe the peripherals.
            for test_name, _, i2c_port in self.probe_list:
                bus_status = controller.send_and_check_status(
                    eval(i2c_port), [])
                factory.log("[%s] at port [%s] tested, returned %d" % (
                            test_name, i2c_port, bus_status))
                if bus_status == usb_to_i2c.I2CController.I2C_OK:
                    self.update_status(test_name, True)
                else:
                    self.update_status(test_name, False)
        except Exception as e:
            factory.log('Exception - %s' % e)

    def perform_audio(self):
        # Repeat several times, if one of them is succeed, mark as a PASS.
        self.update_status('audio', 'FAILED - freq not match')
        for i in range(self.play_repeat):
            error_ret = self.audio_loopback(
                test_freq=self.play_freq,
                tolerance=self.play_tolerance,
                loop_duration=self.play_duration,
                audiofuntest=self.use_audiofuntest)
            self.log_to_file.write('On %d audio loopback, got : %s\n' % (
                i, pprint.pformat(error_ret)))
            self._event_log.Log(
                'connectivity_audio', ab_serial_number=self.serial_number,
                repeated=i, audio_result=error_ret)
            if len(error_ret) == 0:
                self.update_status('audio', 'PASSED')
                break
            else :
                self.update_status('audio', 'FAILED')

        self.advance_state()

    def set_brightness(self, brightness):
        if not self.run_cmd(BRIGHTNESS_CONTROL_CMD % brightness, '^$'):
            raise error.TestNAError('Failed to set brightness')

    def setup_display_test(self):
        # TODO(itspeter): setup the external display related test.
        self.display_config = self.config['display']
        if 'brightness_control' in self.display_config:
            self.brightness_control = int(
                self.display_config['brightness_control'])
        else:
            self.brightness_control = None
        # Prepare the status row.
        self._status_rows.append(('display', 'Display panel', True))
        self._results_to_check.append('display')

        self.display_widget = self.make_decision_widget(
            message=_MESSAGE_DISPLAY,
            key_action_mapping={
                gtk.keysyms.Return: (self.end_display_test, [False]),
                gtk.keysyms.Tab: (self.end_display_test, [True])})

    def perform_display_test(self):
        if self.brightness_control:
            self.set_brightness(self.brightness_control)

    def end_display_test(self, result):
        self.update_status('display', result)
        if self.brightness_control:
            self.set_brightness(0)
        self.advance_state()

    def on_usb_insert(self, dev_path):
        if self.current_state == self._STATE_WAIT_USB:
            self.dev_path = dev_path
            with MountedMedia(dev_path, 1) as config_dir:
                # Load configuration.
                config_path = os.path.join(config_dir, self.config_file)
                self.config = self.base_config.Read(config_path)
                if 'is_internal' in self.config:
                    self.is_internal = True
                else:
                    self.is_internal = False
                # Configure the items
                factory.log('Config loaded. Setup the UI...')
                self.setup_tests()
                self.advance_state()

    def on_usb_remove(self, dev_path):
        if self.current_state != self._STATE_WAIT_USB:
            raise error.TestNAError('USB removal is not allowed during test')

    def on_sn_keypress(self, entry, key):
        if key.keyval == gtk.keysyms.Tab:
            entry.set_text(_TEST_SN_NUMBER)
            return True
        return False

    def on_sn_complete(self, serial_number):
        self.serial_number = serial_number
        self._event_log.Log(
            'connectivity_start', ab_serial_number=self.serial_number)
        self.log_to_file.write('Serial_number : %s\n' % serial_number)
        self.log_to_file.write('Started at : %s\n' % datetime.datetime.now())
        self.update_status('sn', serial_number)
        self.advance_state()

    def run_cmds(self, cmd_tuples):
        '''Executes consecutive commands.

        Args:
            cmd_tuples: a list of tuple in following format:
                        (command, expected regular expression)
        '''
        for cmd_tuple in cmd_tuples:
            cmd, expect_re = cmd_tuple
            self.run_cmd(cmd, expect_re)

    def run_cmd(self, cmd, expect_result):
        '''Runs a command line and compare with expect_result.

        Args:
            cmd: The command to execute.
            expect_result: Expected result in regular expression.

        Return:
            True if the result matches.
        '''
        factory.log('Running command [%s]' % cmd)
        ret = exception_str = ''
        try:
            ret = utils.system_output(cmd)
            factory.log('Command returns [%s, expecting %s]' % (
                ret, expect_result))
            if re.search(expect_result, ret, re.MULTILINE):
                self._event_log.Log(
                    'connectivity_command', ab_serial_number=self.serial_number,
                    status='PASSED', command=cmd,
                    expecting=expect_result, ret=ret)
                return True
        except Exception as e:
            exception_str = '%s' % e
            factory.log('Command failed with exception - %s' % exception_str)
        self._event_log.Log(
            'connectivity_command', ab_serial_number=self.serial_number,
            status='FAILED', exception=exception_str,
            command=cmd, expecting=expect_result, ret=ret)
        return False

    def write_log(self):
        self.generate_final_result()

        # Executes additional commands to external fixture.
        if self.fixture_config and 'ending' in self.fixture_config:
            self.run_cmds(self.fixture_config['ending'])

        self._event_log.Log(
            'connectivity_end', ab_serial_number=self.serial_number,
            result=self.display_dict)
        self.log_to_file.write('Result in summary:\n%s\n' %
                               pprint.pformat(self.display_dict))
        try:
            self.write_to_usb(self.serial_number + '.txt',
                              self.log_to_file.getvalue())
        except Exception as e:
            raise error.TestNAError(
                'Unable to save current log to USB stick - %s' % e)
        # Switch to result tab.
        self.advance_state()

    def write_to_usb(self, filename, content):
        with MountedMedia(self.dev_path, 1) as mount_dir:
            with open(os.path.join(mount_dir, filename), 'a') as f:
                f.write(content)
        factory.log('Log wrote with filename[ %s ].' % filename)

    def prepare_for_next_test(self):
        """Prepares for the next test cycle."""
        if self.fixture_config and 'beginning' in self.fixture_config:
            # Executes additional commands to external fixture.
            self.run_cmds(self.fixture_config['beginning'])
        self.reset_data_for_next_test()
        self.advance_state()

    def reset_data_for_next_test(self):
        """Resets internal data for the next testing cycle."""
        self.reset_status_rows()
        self.log_to_file = StringIO.StringIO()
        self.sn_input_widget.get_entry().set_text('')
        factory.log('Data reseted.')

    def audio_loopback(self, test_freq=1000, loop_duration=1,
                       tolerance=100, audiofuntest=True):
        """Tests digital mic function.

        Args:
            test_freq: the frequency to play and test.
            loop_duration: the duration in seconds to record.
            audiofuntest: choose whether testing with audiofuntest
        Return:
            List of error messages generated during test.
        """
        self._ah = audio_helper.AudioHelper(self,
                record_duration=loop_duration)
        if audiofuntest:
            return self.start_audiofuntest()
        else:
            return self.start_audioloop(
                    test_freq=test_freq,
                    tolerance=tolerance, loop_duration=loop_duration)

    def start_audiofuntest(self):
        '''
        Run audiofuntest, more reliable
        '''
        factory.log('Start audiofuntest')
        errors = []
        self._ah.setup_deps(['test_tones'])
        audiofuntest_path = os.path.join(self.autodir, 'deps',
                'test_tones', 'src', 'audiofuntest')
        if not (os.path.exists(audiofuntest_path) and
                os.access(audiofuntest_path, os.X_OK)):
            raise error.TestError(
                   '%s is not an executable' % audiofuntest_path)

        sub_proc = subprocess.Popen([audiofuntest_path, '-r', '48000'],
                stderr=subprocess.PIPE)
        success_rate = 0.0
        while True:
            line = sub_proc.stderr.readline()
            factory.log(line)
            m = _AUDIOFUNTEST_SUCCESS_RATE_RE.match(line)
            if m:
                success_rate = float(m.group(1))
                factory.log('success_rate = %f' % success_rate)

            m = _AUDIOFUNTEST_STOP_RE.match(line)
            if m:
                self._audioresult = success_rate > 50.0
                factory.log(line)
                break

        if ( hasattr(self, '_audioresult') and (self._audioresult is False) ):
             errors.append('Success rate is too low: %.1f\n' %
                           success_rate)
        return errors

    def start_audioloop(self, test_freq=1000, loop_duration=1, tolerance=100):
        '''
        If audiofuntest is not work, change to this test.
        '''
        factory.log('Start audioloop')
        errors = []
        self._ah.setup_deps(['sox'])
        self._ah.set_mixer_controls(
                [{'name': '"Digital-Mic Capture Switch"',
                  'value': 'on'},
                 {'name': '"Digital-Mic Capture Volume"',
                  'value': '100,100'},
                 {'name': '"Speaker Playback Volume"',
                  'value': '100,100'}])

        # Callbacks for sound playback and record result check.
        def playback_sine():
            cmd = '%s -n -d synth %d sine %d' % (self._ah.sox_path,
                    loop_duration, test_freq)
            utils.system(cmd)

        def check_loop_output(sox_output):
            freq = self._ah.get_rough_freq(sox_output)
            factory.log('Got freq %d' % freq)
            if abs(freq - test_freq) > tolerance:
                errors.append('Frequency not match, expect %d but got %d' %
                        (test_freq, freq))

        with tempfile.NamedTemporaryFile(mode='w+t') as noise_file:
            self._ah.record_sample(noise_file.name)
            self._ah.loopback_test_channels(noise_file.name,
                    lambda ch: playback_sine(),
                    check_loop_output)
        return errors

    def run_once(self, config_file):
        # Initial EventLog
        self._event_log = EventLog.ForAutoTest()
        self.serial_number = 'Initialize'

        factory.log('%s run_once' % self.__class__)
        # Display dual screen if external display is connected.
        self.run_cmd('xrandr --auto', '')
        # Disable power management.
        self.run_cmd('stop powerd', 'powerd stop')
        # Initialize variables.
        self.config_file = config_file
        self.base_config = PluggableConfig({})

        # Set up the USB prompt widgets.
        self.usb_prompt_widget = self.make_decision_widget(
            message=_MESSAGE_USB, key_action_mapping=[])

        self.prepare_panel_widget = self.make_decision_widget(
            message=_MESSAGE_PREPARE_PANEL,
            key_action_mapping={
                gtk.keysyms.Return: (self.prepare_for_next_test, [])})
        # States after "prepare panel" will be configured in setup_test, after
        # configuration on external media (USB/SD) is loaded.
        self._STATE_WAIT_USB = self.register_state(self.usb_prompt_widget)
        self._STATE_PREPARE_PANEL = self.register_state(
            self.prepare_panel_widget, None)
        # Setup the usb monitor.
        monitor = MediaMonitor()
        monitor.start(on_insert=self.on_usb_insert,
                      on_remove=self.on_usb_remove)
        self.start_state_machine(self._STATE_WAIT_USB)
