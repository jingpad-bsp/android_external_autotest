# -*- coding: utf-8 -*-
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import gtk
import logging
import os
import pprint
import StringIO

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory_setup_modules
from cros.factory.test import factory
from cros.factory.test import task
from cros.factory.test import ui as ful
from cros.factory.test.media_util import MediaMonitor
from cros.factory.test.media_util import MountedMedia
from autotest_lib.client.cros.rf import agilent_scpi
from autotest_lib.client.cros.rf import rf_utils
from autotest_lib.client.cros.rf.config import PluggableConfig

COLOR_MAGENTA = gtk.gdk.color_parse('magenta1')

_MESSAGE_USB = (
    'Please insert the usb stick to load parameters.\n'
    '請插入usb以讀取測試參數\n')
_MESSAGE_PREPARE_PANEL = (
    'Please place the LCD panel into the fixture.\n'
    'Then press ENTER to scan the barcode.\n'
    '請放置LCD本體在治具上\n'
    '完成后按ENTER\n')
_MESSAGE_ENTER_SN_HINT = ('Scan barcode on LCD.\n掃描LCD本體上S/N:')
_MESSAGE_PREPARE_MAIN_ANTENNA = (
    'Make sure the main WWAN antennta is connected to Port 1\n'
    'Make sure the main WLAN antennta is connected to Port 2\n'
    'Then press key "A" to next stage.\n'
    '連接 主WWAN天線至 Port 1\n'
    '連接 主WLAN天線至 Port 2\n'
    '完成後按"A"鍵\n')
_MESSAGE_TEST_IN_PROGRESS_MAIN = (
    'Testing MAIN antenna...\n'
    '測試 主天線 中...\n')
_MESSAGE_PREPARE_AUX_ANTENNA = (
    'Make sure the aux WWAN antennta is connected to Port 1\n'
    'Make sure the aux WLAN antennta is connected to Port 2\n'
    'Then press key "K" to next stage.\n'
    '連接 副WWAN天線至 Port 1\n'
    '連接 副WLAN天線至 Port 2\n'
    '完成後按"K"鍵\n')
_MESSAGE_TEST_IN_PROGRESS_AUX = (
    'Testing AUX antenna...\n'
    '測試 副天線 中...\n')
_MESSAGE_WRITING_IN_PROGRESS = (
    'Writing log....\n'
    '記錄中...\n')
_MESSAGE_RESULT_TAB = (
    'Results are listed below.\n'
    'Please disconnect the panel and press ENTER to write log.\n'
    '測試結果顯示如下\n'
    '請將AB Panel移除, 並按ENTER完成測試\n')

_TEST_SN_NUMBER = 'TEST-SN-NUMBER'
_LABEL_SIZE = (300, 30)


def make_status_row(row_name,
                    display_dict,
                    init_prompt=None,
                    init_status=None):
    """Returns a HBox shows the status."""
    display_dict.setdefault(row_name, {})
    if init_prompt is None:
        init_prompt = display_dict[row_name]['prompt']
    else:
        display_dict[row_name]['prompt'] = init_prompt
    if init_status is None:
        init_status = display_dict[row_name]['status']
    else:
        display_dict[row_name]['status'] = init_status

    def prompt_label_expose(widget, event):
        prompt = display_dict[row_name]['prompt']
        widget.set_text(prompt)

    def status_label_expose(widget, event):
        status = display_dict[row_name]['status']
        widget.set_text(status)
        widget.modify_fg(gtk.STATE_NORMAL, ful.LABEL_COLORS[status])

    prompt_label = ful.make_label(
            init_prompt, size=_LABEL_SIZE,
            alignment=(0, 0.5))
    delimiter_label = ful.make_label(':', alignment=(0, 0.5))
    status_label = ful.make_label(
            init_status, size=_LABEL_SIZE,
            alignment=(0, 0.5), fg=ful.LABEL_COLORS[init_status])

    widget = gtk.HBox()
    widget.pack_end(status_label, False, False)
    widget.pack_end(delimiter_label, False, False)
    widget.pack_end(prompt_label, False, False)

    status_label.connect('expose_event', status_label_expose)
    prompt_label.connect('expose_event', prompt_label_expose)
    return widget


def make_prepare_widget(message,
                        on_key_continue, keys_to_continue,
                        on_key_skip=None, keys_to_skip=None,
                        fg_color=ful.LIGHT_GREEN):
    """Returns a widget that display the message and bind proper functions."""
    if keys_to_skip is None:
        keys_to_skip = []

    widget = gtk.VBox()
    widget.add(ful.make_label(message, fg=fg_color))
    def key_release_callback(widget, event):
        if on_key_continue and event.keyval in keys_to_continue:
            on_key_continue()
            return True
        if on_key_skip and event.keyval in keys_to_skip:
            on_key_skip()
            return True

    widget.key_callback = key_release_callback
    return widget


class factory_Antenna(test.test):
    version = 4

    # The state goes from _STATE_INITIAL to _STATE_RESULT_TAB then jumps back
    # to _STATE_PREPARE_PANEL for another testing cycle.
    _STATE_INITIAL = -1
    _STATE_WAIT_USB = 0
    _STATE_PREPARE_PANEL = 1
    _STATE_ENTERING_SN = 2
    _STATE_PREPARE_MAIN_ANTENNA = 3
    _STATE_TEST_IN_PROGRESS_MAIN = 4
    _STATE_PREPARE_AUX_ANTENNA = 5
    _STATE_TEST_IN_PROGRESS_AUX = 6
    _STATE_WRITING_IN_PROGRESS = 7
    _STATE_RESULT_TAB = 8

    # Status in the final result tab.
    _STATUS_NAMES = ['sn', 'cell_main', 'cell_aux',
                     'wifi_main', 'wifi_aux', 'result']
    _STATUS_LABELS = ['1.Serial Number',
                      '2.Cellular Antenna(MAIN)',
                      '3.Cellular Antenna(AUX)',
                      '4.WiFi Antenna(MAIN)',
                      '5.WiFi Antenna(AUX)',
                      '6.Test Result']
    _RESULTS_TO_CHECK = ['sn', 'cell_main', 'cell_aux',
                         'wifi_main', 'wifi_aux']

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

    def on_usb_insert(self, dev_path):
        if self._state == self._STATE_WAIT_USB:
            self.dev_path = dev_path
            with MountedMedia(dev_path, 1) as config_dir:
                config_path = os.path.join(config_dir, 'antenna.params')
                self.config = self.base_config.Read(config_path)
                factory.log("Config loaded.")
                self.advance_state()

    def on_usb_remove(self, dev_path):
        if self._state != self._STATE_WAIT_USB:
            raise error.TestNAError("USB removal is not allowed during test")

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
        self.log_to_file.write('Serial_number : %s\n' % serial_number)
        self.log_to_file.write('Started at : %s\n' % datetime.datetime.now())
        # TODO(itspeter): display the SN info in the result tab.
        self._update_status('sn', self.check_sn_format(serial_number))
        self.advance_state()

    @staticmethod
    def check_sn_format(sn):
        # TODO(itspeter): Check SN according to the spec in factory.
        return sn == _TEST_SN_NUMBER

    def write_to_usb(self, filename, content):
        with MountedMedia(self.dev_path, 1) as mount_dir:
            with open(os.path.join(mount_dir, filename), 'w') as f:
                f.write(content)
        factory.log("Log wrote with SN: %s." % self.serial_number)

    def test_main_antennas(self):
        freqs = set()
        self._add_required_freqs('cell', freqs)
        self._add_required_freqs('wifi', freqs)
        ret = self._get_traces(freqs, ['S11', 'S22'],
                               purpose='test_main_antennas')
        self._test_main_cell_antennas(ret)
        self._test_main_wifi_antennas(ret)
        self.advance_state()

    def test_aux_antennas(self):
        freqs = set()
        self._add_required_freqs('cell', freqs)
        self._add_required_freqs('wifi', freqs)
        ret = self._get_traces(freqs, ['S11', 'S22'],
                               purpose='test_aux_antennas')
        self._test_aux_cell_antennas(ret)
        self._test_aux_wifi_antennas(ret)
        self.generate_final_result()

    def _update_status(self, row_name, result):
        """Updates status in display_dict."""
        result_map = {
            True: ful.PASSED,
            False: ful.FAILED,
            None: ful.UNTESTED
        }
        assert result in result_map, "Unknown result"
        self.display_dict[row_name]['status'] = result_map[result]

    def _test_main_cell_antennas(self, traces):
        self._update_status(
            'cell_main',
            self._compare_traces(traces, 'cell', 1, 'cell_main', 'S11'))

    def _test_main_wifi_antennas(self, traces):
        self._update_status(
            'wifi_main',
            self._compare_traces(traces, 'wifi', 1, 'wifi_main', 'S22'))

    def _test_aux_cell_antennas(self, traces):
        self._update_status(
            'cell_aux',
            self._compare_traces(traces, 'cell', 3, 'cell_aux', 'S11'))

    def _test_aux_wifi_antennas(self, traces):
        self._update_status(
            'wifi_aux',
            self._compare_traces(traces, 'wifi', 3, 'wifi_aux', 'S22'))

    def generate_final_result(self):
        self._result = all(
           ful.PASSED == self.display_dict[var]['status']
           for var in self._RESULTS_TO_CHECK)
        self._update_status('result', self._result)
        self.log_to_file.write("Result in summary:\n%s\n" %
                               pprint.pformat(self.display_dict))
        # Save logs and hint user it is writing in progress.
        self.advance_state()

    def save_log(self):
        # TODO(itspeter): Dump more details upon RF teams' request.
        self.log_to_file.write("\n\nRaw traces:\n%s\n" %
                               pprint.pformat(self._raw_traces))
        try:
            self.write_to_usb(self.serial_number + ".txt",
                              self.log_to_file.getvalue())
        except Exception as e:
            raise error.TestNAError(
                "Unable to save current log to USB stick - %s" % e)

        # Switch to the result widget
        self.advance_state()

    def _check_measurement(self, standard_value, extracted_value):
        """Compares whether the measurement meets the spec."""
        if (standard_value is None) or (extracted_value <  standard_value):
            return True
        else:
            return False

    def _add_required_freqs(self, antenna_type, freqs_set):
        """Reads the required frequencies and add it to freqs_set.

        Format of antenna.params:
        {'vswr_max': {antenna_type: [(freq, main, coupling, aux), ...
        For example: {'vswr_max': {'cell': [(746, -6, -10, -6),

        Usage example:
            self._add_required_freqs('cell', freqs)
        """
        for config_tuple in self.config['vswr_max'][antenna_type]:
            freqs_set.add(config_tuple[0])

    def _get_traces(self, freqs_set, parameters, purpose="unspecified"):
        """This function is a wrapper for GetTraces in order to log details."""
        # Generate the sweep tuples.
        freqs = sorted(freqs_set)
        segments = [(freq_min * 1e6, freq_max * 1e6, 2) for
                    freq_min, freq_max in
                    zip(freqs, freqs[1:])]

        self.ena.SetSweepSegments(segments)
        ret = self.ena.GetTraces(parameters)
        self._raw_traces[purpose] = ret
        return ret

    def _compare_traces(self, traces, antenna_type, column,
                        log_title, ena_parameter):
        """Compares whether returned traces and the spec are aligned.

        Usage example:
            self._test_sweep_segment(traces, 'cell', 1, 'cell_main', 'S11')
        """
        self.log_to_file.write(
            "Start measurement [%s], with profile[%s,col %s], from ENA-%s\n" %
            (log_title, antenna_type, column, ena_parameter))
        # Generate the sweep tuples.
        freqs = [atuple[0] * 1e6 for atuple in
                 self.config['vswr_max'][antenna_type]]
        standards = [atuple[column] for atuple in
                     self.config['vswr_max'][antenna_type]]
        freqs_responses = [traces.GetFreqResponse(freq, ena_parameter) for
                           freq in freqs]
        results = [self._check_measurement(std_val, ext_val) for
                   std_val, ext_val in
                   zip(standards, freqs_responses)]
        logs = zip(freqs, standards, freqs_responses, results)
        logs.insert(0, ("Frequency",
                        "Column-%s" % column,
                        "ENA-%s" % ena_parameter,
                        "Result"))
        self.log_to_file.write("%s results:\n%s\n" %
                               (log_title, pprint.pformat(logs)))
        return all(results)

    def reset_data_for_next_test(self):
        """Resets internal data for the next testing cycle.

        prepare_panel_widget is the first widget of a new testing cycle. This
        function resets all the testing data. Caller should call switch_widget
        to change current UI to the first widget.
        """
        self.log_to_file = StringIO.StringIO()
        self._raw_traces = {}
        self.sn_input_widget.get_entry().set_text('')
        for var in self._STATUS_NAMES:
            self._update_status(var, None)
        factory.log("Reset internal data.")

    def on_result_enter(self):
        self.advance_state()
        return True

    def switch_to_sn_input_widget(self):
        self.advance_state()
        return True

    def make_result_widget(self, on_key_enter):
        widget = gtk.VBox()
        widget.add(ful.make_label(_MESSAGE_RESULT_TAB))
        for name, label in zip(self._STATUS_NAMES, self._STATUS_LABELS):
            widget.add(make_status_row(name, self.display_dict,
                                       label, ful.UNTESTED))
        def key_press_callback(widget, event):
            if event.keyval == gtk.keysyms.Return:
                on_key_enter()

        widget.key_callback = key_press_callback
        return widget

    def run_once(self, ena_host, local_ip=None):
        factory.log('%s run_once' % self.__class__)
        factory.log('parameters: (ena_host: %s, local_ip: %s)' %
                    (ena_host, local_ip))
        # Setup the local ip address
        if local_ip:
            factory.log('Setup the local ip address to %s' % local_ip)
            rf_utils.SetEthernetIp(local_ip)

        # Setup the ENA host.
        factory.log('Connecting to the ENA...')
        self.ena = agilent_scpi.ENASCPI(ena_host)
        # Initialize variables.
        self.display_dict = {}
        self.base_config = PluggableConfig({})
        self.last_handler = None
        # Set up the UI widgets.
        self.usb_prompt_widget = gtk.VBox()
        self.usb_prompt_widget.add(ful.make_label(_MESSAGE_USB))
        self.prepare_panel_widget = make_prepare_widget(
            message=_MESSAGE_PREPARE_PANEL,
            on_key_continue=self.switch_to_sn_input_widget,
            keys_to_continue=[gtk.keysyms.Return])

        self.prepare_main_antenna_widget = make_prepare_widget(
            message=_MESSAGE_PREPARE_MAIN_ANTENNA,
            fg_color=COLOR_MAGENTA,
            on_key_continue=self.advance_state,
            keys_to_continue=[ord('A'), ord('a')])

        self.testing_main_widget = make_prepare_widget(
            message=_MESSAGE_TEST_IN_PROGRESS_MAIN,
            on_key_continue=None,
            keys_to_continue=[])

        self.prepare_aux_antenna_widget = make_prepare_widget(
            message=_MESSAGE_PREPARE_AUX_ANTENNA,
            fg_color=COLOR_MAGENTA,
            on_key_continue=self.advance_state,
            keys_to_continue=[ord('K'), ord('k')])

        self.testing_aux_widget = make_prepare_widget(
            message=_MESSAGE_TEST_IN_PROGRESS_AUX,
            on_key_continue=None,
            keys_to_continue=[])

        self.writing_widget = make_prepare_widget(
            message=_MESSAGE_WRITING_IN_PROGRESS,
            fg_color=COLOR_MAGENTA,
            on_key_continue=None,
            keys_to_continue=[])
        self.result_widget = self.make_result_widget(self.on_result_enter)

        self.sn_input_widget = ful.make_input_window(
                prompt=_MESSAGE_ENTER_SN_HINT,
                on_validate=None,
                on_keypress=self.on_sn_keypress,
                on_complete=self.on_sn_complete)
        # Make sure the entry in widget will have focus.
        self.sn_input_widget.connect(
            "show",
            lambda *x : self.sn_input_widget.get_entry().grab_focus())

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
            self._STATE_PREPARE_MAIN_ANTENNA:
                (self.prepare_main_antenna_widget, None),
            self._STATE_TEST_IN_PROGRESS_MAIN:
                (self.testing_main_widget, self.test_main_antennas),
            self._STATE_PREPARE_AUX_ANTENNA:
                (self.prepare_aux_antenna_widget, None),
            self._STATE_TEST_IN_PROGRESS_AUX:
                (self.testing_aux_widget, self.test_aux_antennas),
            self._STATE_WRITING_IN_PROGRESS:
                (self.writing_widget, self.save_log),
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
