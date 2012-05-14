# -*- coding: utf-8 -*-
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import gtk
import os
import pprint
import StringIO

from autotest_lib.client.cros import factory
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.camera.camera_preview import CameraPreview
from autotest_lib.client.cros.factory import state_machine
from autotest_lib.client.cros.factory.media_util import MediaMonitor
from autotest_lib.client.cros.factory.media_util import MountedMedia
from autotest_lib.client.cros.i2c import usb_to_i2c
from autotest_lib.client.cros.rf.config import PluggableConfig


_MESSAGE_USB = (
    'Please insert the usb stick, adapter board and golden reference.\n'
    '請插入USB隨身碟, 測試板, 良品 以讀取測試參數\n')
_MESSAGE_PREPARE_PANEL = (
    'Please prepare the next AB panel.\n'
    'Be sure all the connector is connected.\n'
    'Press ENTER to execute connectivity test.\n'
    '請連接下一塊AB Panel\n'
    '備妥後按ENTER執行測試\n')
_MESSAGE_ENTER_SN_HINT = ('Please scan SN on LCD.\n請掃描本體上S/N:')
_MESSAGE_CAMERA_CHECK = (
    'hit TAB to pass and ENTER to fail.\n' +
    '成功請按 TAB, 錯誤請按 ENTER.\n')
_MESSAGE_I2C_TESTING = (
    'I2C testing...\n'
    '測試中...\n')
_MESSAGE_WRITING_LOGS = (
    'Writing logs...\n'
    '紀錄中...\n')
_MESSAGE_RESULT_TAB = (
    'Results are listed below.\n'
    'Please disconnect the panel.\n'
    '測試結果顯示如下\n'
    '請將AB Panel移除\n')

_TEST_SN_NUMBER = 'TEST-SN-NUMBER'
COLOR_MAGENTA = gtk.gdk.color_parse('magenta1')

class factory_Connector(state_machine.FactoryStateMachine):
    version = 3

    def setup_tests(self):
        # Setup serial number input widget.
        self.sn_input_widget = self.make_serial_number_widget(
            message=_MESSAGE_ENTER_SN_HINT,
            default_validate_regex=self.config['sn_regex'],
            on_complete=self.on_sn_complete,
            on_keypress=self.on_sn_keypress,
            generate_status_row=True)
        self.i2c_testing_widget = self.make_decision_widget(
            message=_MESSAGE_I2C_TESTING, key_action_mapping={})
        self.writing_widget = self.make_decision_widget(
            message=_MESSAGE_WRITING_LOGS,
            key_action_mapping={},
            fg_color=COLOR_MAGENTA)

        self.setup_camera_preview()
        self.setup_i2c_bus()
        # TODO(itspeter): setup the external display related test.

        # Setup result tab.
        self.result_widget = self.make_result_widget(
            _MESSAGE_RESULT_TAB,
            key_action_mapping={
                gtk.keysyms.Return: (self.advance_state, [])})
        # Register more states for test procedure with configuration data
        # loaded from external media device (USB/SD).
        self.register_state(self.sn_input_widget)
        self.register_state(self.preview_widget)
        self.register_state(self.i2c_testing_widget, None,
                            self.perform_i2c_bus_test)
        self.register_state(self.writing_widget, None, self.write_log)
        # After this state (result), go back to "prepare panel" state.
        self.register_state(self.result_widget, None, None,
                            self._STATE_PREPARE_PANEL)

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

    def setup_i2c_bus(self):
        self.bus_config = self.config['bus']
        factory.log('I2C bus config is [%s]' % self.bus_config)
        self.i2c_list = self.bus_config['i2c_list']
        self.chipset = self.bus_config['chipset']
        # Prepare the status row.
        for test_name, test_label, _ in self.i2c_list:
            self._status_rows.append((test_name, test_label, True))
            self._results_to_check.append(test_name)

    def perform_i2c_bus_test(self):
        try:
            controller = usb_to_i2c.create_i2c_controller(self.chipset)
            # Turn on the led light to indicate test in progress.
            # http://www.nxp.com/documents/data_sheet/SC18IM700.pdf
            controller.send_and_check_status(
                98, [0x11, 0x97, 0x80, 0x00, 0x40, 0xE1])
            # Probe the peripherals.
            for test_name, _, i2c_port in self.i2c_list:
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
        self.advance_state()

    def on_usb_insert(self, dev_path):
        if self.current_state == self._STATE_WAIT_USB:
            self.dev_path = dev_path
            with MountedMedia(dev_path, 1) as config_dir:
                # Load configuration.
                config_path = os.path.join(config_dir, 'connectivity.params')
                self.config = self.base_config.Read(config_path)
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
        self.log_to_file.write('Serial_number : %s\n' % serial_number)
        self.log_to_file.write('Started at : %s\n' % datetime.datetime.now())
        self.update_status('sn', serial_number)
        self.perform_camera_preview()

    def perform_camera_preview(self):
        try:
            self.camera_preview.init_device(
                int(self.camera_config['DEVICE_INDEX']))
        except IOError as e:
            factory.log('Cannot get cammera - %s' % e)
        finally:
            self.advance_state()

    def write_log(self):
        self.generate_final_result()
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


    def reset_data_for_next_test(self):
        """Resets internal data for the next testing cycle."""
        self.reset_status_rows()
        self.log_to_file = StringIO.StringIO()
        self.sn_input_widget.get_entry().set_text('')
        factory.log('Data reseted.')

    def run_once(self):
        factory.log('%s run_once' % self.__class__)
        # Initialize variables.
        self.base_config = PluggableConfig({})

        # Set up the USB prompt widgets.
        self.usb_prompt_widget = self.make_decision_widget(
            message=_MESSAGE_USB, key_action_mapping=[])

        self.prepare_panel_widget = self.make_decision_widget(
            message=_MESSAGE_PREPARE_PANEL,
            key_action_mapping={
                gtk.keysyms.Return: (self.advance_state, [])})
        # States after "prepare panel" will be configured in setup_test, after
        # configuration on external media (USB/SD) is loaded.
        self._STATE_WAIT_USB = self.register_state(self.usb_prompt_widget)
        self._STATE_PREPARE_PANEL = self.register_state(
            self.prepare_panel_widget, None,
            self.reset_data_for_next_test)
        # Setup the usb monitor.
        monitor = MediaMonitor()
        monitor.start(on_insert=self.on_usb_insert,
                      on_remove=self.on_usb_remove)
        self.start_state_machine(self._STATE_WAIT_USB)
