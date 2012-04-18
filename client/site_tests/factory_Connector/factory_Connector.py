# -*- coding: utf-8 -*-
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import gtk
import os
import pprint
import re
import StringIO

from autotest_lib.client.bin import test
from autotest_lib.client.cros import factory
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.cros.camera.camera_preview import CameraPreview
from autotest_lib.client.cros.factory import task
from autotest_lib.client.cros.factory import ui as ful
from autotest_lib.client.cros.factory.media_util import MediaMonitor
from autotest_lib.client.cros.factory.media_util import MountedMedia
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
_MESSAGE_WRITING_LOGS = (
    'Writing logs...\n'
    '紀錄中...\n')
_MESSAGE_RESULT_TAB = (
    'Results are listed below.\n'
    'Please disconnect the panel.\n'
    '測試結果顯示如下\n'
    '請將AB Panel移除\n')

_TEST_SN_NUMBER = 'TEST-SN-NUMBER'
_LABEL_SIZE = (300, 30)
COLOR_MAGENTA = gtk.gdk.color_parse('magenta1')

def make_prepare_widget(message,
                        key_action_mapping,
                        fg_color=ful.LIGHT_GREEN):
    """Returns a widget that display the message and bind proper functions."""
    widget = gtk.VBox()
    widget.add(ful.make_label(message, fg=fg_color))
    def key_release_callback(widget, event):
        if event.keyval in key_action_mapping:
            if key_action_mapping[event.keyval] is not None:
                key_action_mapping[event.keyval]()
                return True

    widget.key_callback = key_release_callback
    return widget


class factory_Connector(test.test):
    version = 1

    # The state goes from _STATE_INITIAL to _STATE_RESULT_TAB then jumps back
    # to _STATE_PREPARE_PANEL for another testing cycle.
    _STATE_INITIAL = -1
    _STATE_WAIT_USB = 0
    _STATE_PREPARE_PANEL = 1
    _STATE_ENTERING_SN = 2
    _STATE_CAMERA_CHECK = 3
    _STATE_WRITING_LOGS = 4
    _STATE_RESULT_TAB = 5

    def advance_state(self):
        if self._state == self._STATE_RESULT_TAB:
            self._state = self._STATE_PREPARE_PANEL
        else:
            self._state = self._state + 1
        # Update the UI.
        widget, callback = self._state_widget[self._state]
        self.switch_widget(widget)
        # Create an event to invoke function after UI is updated.
        if callback:
            task.schedule(callback)

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

    def make_result_widget(self, on_key_enter):
        self._status_names.append('result')
        self._status_labels.append('Result')

        widget = gtk.VBox()
        widget.add(ful.make_label(_MESSAGE_RESULT_TAB))

        self.display_dict = {}
        for name, label in zip(self._status_names, self._status_labels):
            td, tw = ful.make_status_row(label, ful.UNTESTED, _LABEL_SIZE)
            self.display_dict[name] = td
            widget.add(tw)

        def key_press_callback(widget, event):
            if event.keyval == gtk.keysyms.Return:
                on_key_enter()
                return True
        widget.key_callback = key_press_callback

        # Update the states map.
        self.result_widget = widget
        self._state_widget[self._STATE_RESULT_TAB] = (self.result_widget, None)

    def setup_tests(self):
        self.setup_camera_preview()
        # TODO(itspeter): setup the i2c bus related test.
        # TODO(itspeter): setup the external display related test.
        # Setup result tab.
        self.make_result_widget(self.advance_state)

    def setup_camera_preview(self):
        self.camera_config = self.config['camera']
        factory.log('Camera config is [%s]' % self.camera_config)
        # Prepare the status row.
        self._status_names.append('camera')
        self._status_labels.append('Camera Preview')
        self._results_to_check.append('camera')
        # Setup preview widget
        self.camera_preview = CameraPreview(
            key_action_mapping={gtk.keysyms.Tab: self.pass_preview_test,
                                gtk.keysyms.Return: self.fail_preview_test},
            msg=_MESSAGE_CAMERA_CHECK,
            width=int(self.camera_config['WIDTH']),
            height=int(self.camera_config['HEIGHT']))
        # Updates the states map.
        self.preview_widget = self.camera_preview.widget
        self._state_widget[self._STATE_CAMERA_CHECK] = (self.preview_widget,
                                                        None)

    def pass_preview_test(self):
        self.camera_preview.capture_stop()
        factory.log('Preview passed.')
        self._update_status('camera', True)
        self.advance_state()

    def fail_preview_test(self):
        self.camera_preview.capture_stop()
        factory.log('Preview failed.')
        self._update_status('camera', False)
        self.advance_state()

    def on_usb_insert(self, dev_path):
        if self._state == self._STATE_WAIT_USB:
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
        if self._state != self._STATE_WAIT_USB:
            raise error.TestNAError('USB removal is not allowed during test')

    def register_callbacks(self, window):
        def key_press_callback(widget, event):
            if hasattr(self, 'last_widget'):
                if hasattr(self.last_widget, 'key_callback'):
                    return self.last_widget.key_callback(widget, event)
            return False
        window.connect('key-press-event', key_press_callback)
        window.add_events(gtk.gdk.KEY_PRESS_MASK)

    def on_sn_keypress(self, entry, key):
        if key.keyval == gtk.keysyms.Tab:
            entry.set_text(_TEST_SN_NUMBER)
            return True
        return False

    def on_sn_complete(self, serial_number):
        self.serial_number = serial_number
        self.log_to_file.write('Serial_number : %s\n' % serial_number)
        self.log_to_file.write('Started at : %s\n' % datetime.datetime.now())
        self._update_status('sn', self.check_sn_format(serial_number))
        self.perform_camera_preview()

    def check_sn_format(self, sn):
        if re.search(self.config['sn_format'], sn):
            return True
        return False

    def perform_camera_preview(self):
        try:
            self.camera_preview.init_device(
                int(self.camera_config['DEVICE_INDEX']))
        except IOError as e:
            factory.log('Cannot get cammera - %s' % e)
        finally:
            self.advance_state()

    def _update_status(self, row_name, result):
        """Updates status in display_dict."""
        result_map = {
            True: ful.PASSED,
            False: ful.FAILED,
            None: ful.UNTESTED
        }
        assert result in result_map, 'Unknown result'
        self.display_dict[row_name]['status'] = result_map[result]


    def generate_final_result(self):
        self._result = all(
           ful.PASSED == self.display_dict[var]['status']
           for var in self._results_to_check)
        self._update_status('result', self._result)
        self.log_to_file.write('Result in summary:\n%s\n' %
                               pprint.pformat(self.display_dict))
        self.save_log()
        # Switch to result tab.
        self.advance_state()

    def write_to_usb(self, filename, content):
        with MountedMedia(self.dev_path, 1) as mount_dir:
            with open(os.path.join(mount_dir, filename), 'a') as f:
                f.write(content)
        factory.log('Log wrote with filename[ %s ].' % filename)
        return True

    def save_log(self):
        try:
            self.write_to_usb(self.serial_number + '.txt',
                              self.log_to_file.getvalue())
        except Exception as e:
            raise error.TestNAError(
                'Unable to save current log to USB stick - %s' % e)

    def reset_data_for_next_test(self):
        """Resets internal data for the next testing cycle."""
        factory.log('Data reseted.')
        self.log_to_file = StringIO.StringIO()
        self.sn_input_widget.get_entry().set_text('')
        for var in self._status_names:
            self._update_status(var, None)

    def switch_to_sn_input_widget(self):
        self.advance_state()
        return True

    def run_once(self, set_interface_ip=None):
        factory.log('%s run_once' % self.__class__)
        # Initialize variables.
        self._status_names = ['sn']
        self._status_labels = ['Serial Number']
        self._results_to_check = ['sn']
        self.base_config = PluggableConfig({})
        self.last_handler = None

        # Set up the USB prompt widgets.
        self.usb_prompt_widget = make_prepare_widget(
            message=_MESSAGE_USB, key_action_mapping=[])

        self.prepare_panel_widget = make_prepare_widget(
            message=_MESSAGE_PREPARE_PANEL,
            key_action_mapping={gtk.keysyms.Return: self.advance_state})

        self.sn_input_widget = ful.make_input_window(
            prompt=_MESSAGE_ENTER_SN_HINT,
            on_validate=self.check_sn_format,
            on_keypress=self.on_sn_keypress,
            on_complete=self.on_sn_complete)
        # Make sure the entry in widget will have focus.
        self.sn_input_widget.connect(
            'show',
            lambda *x : self.sn_input_widget.get_entry().grab_focus())

        self.preview_widget = None

        self.writing_widget = make_prepare_widget(
            message=_MESSAGE_WRITING_LOGS,
            key_action_mapping=[],
            fg_color=COLOR_MAGENTA)

        self.result_widget = None
        # Setup the map of state transition rules,
        # in {STATE: (widget, callback)} format.
        self._state_widget = {
            self._STATE_INITIAL:
                (None, None),
            self._STATE_WAIT_USB:
                (self.usb_prompt_widget, None),
            self._STATE_PREPARE_PANEL:
                (self.prepare_panel_widget, self.reset_data_for_next_test),
            self._STATE_ENTERING_SN:
                (self.sn_input_widget, None),
            self._STATE_CAMERA_CHECK:
                (self.preview_widget, None),
            self._STATE_WRITING_LOGS:
                (self.writing_widget, self.generate_final_result),
            self._STATE_RESULT_TAB:
                (self.result_widget, None)
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
