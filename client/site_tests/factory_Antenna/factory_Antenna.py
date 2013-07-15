# -*- coding: utf-8 -*-
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import gtk
import logging
import os
import pprint
import re
import shutil
import time
import StringIO


from urllib import urlopen
from xmlrpclib import Binary


from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
#pylint: disable=W0611
from autotest_lib.client.cros import factory_setup_modules
from cros.factory.event_log import EventLog
try:
    # Workaround to avoid not finding jsonrpclib in buildbot.
    from cros.factory.goofy.connection_manager import PingHost
    from cros.factory.goofy.goofy import CACHES_DIR
except:
    pass
from cros.factory.rf.e5071c_scpi import ENASCPI
from cros.factory.rf.utils import DownloadParameters, CheckPower
from cros.factory.test import factory
from cros.factory.test import shopfloor
from cros.factory.test import task
from cros.factory.test import ui as ful
from cros.factory.test.media_util import MediaMonitor
from cros.factory.test.media_util import MountedMedia
from cros.factory.utils.net_utils import FindUsableEthDevice
from cros.factory.utils.process_utils import Spawn, SpawnOutput
from autotest_lib.client.cros.rf import rf_utils
from autotest_lib.client.cros.rf.config import PluggableConfig

from cros.factory.test.utils import TimeString, TryMakeDirs


COLOR_MAGENTA = gtk.gdk.color_parse('magenta1')

_MESSAGE_SHOPFLOOR_DOWNLOAD = (
    'Downloading parameters from shopfloor...\n'
    '从Shopfloor下载测试参数中...\n')
_MESSAGE_USB_LOAD_PARAMETERS = (
    'Please insert the usb stick to load parameters and save log.\n'
    '请插入usb以读取测试参数及储存测试纪录\n')
_MESSAGE_USB_LOG_STORAGE = (
    'Please insert the usb stick to save log.\n'
    '请插入usb以储存测试纪录\n')
_MESSAGE_CONNECTING_ENA = (
    'Connecting with the ENA...\n'
    '与ENA(E5071C)连线中\n')
_MESSAGE_CALIBRATION_CHECK = (
    'Checking its calibration status...\n'
    '验证仪器矫正状态\n')
_MESSAGE_PREPARE_PANEL = (
    'Please place the LCD panel into the fixture.\n'
    'Then press ENTER to scan the barcode.\n'
    '请放置LCD本体在治具上\n'
    '完成后按ENTER\n')
_MESSAGE_ENTER_SN_HINT = ('Scan barcode on LCD.\n扫描LCD本体上S/N:')
_MESSAGE_PREPARE_MAIN_ANTENNA = (
    'Make sure the main WWAN antennta is connected to Port 1\n'
    'Make sure the main WLAN antennta is connected to Port 2\n'
    'Then press key "A" to next stage.\n'
    '连接 主WWAN天线至 Port 1\n'
    '连接 主WLAN天线至 Port 2\n'
    '完成后按"A"键\n')
_MESSAGE_TEST_IN_PROGRESS_MAIN = (
    'Testing MAIN antenna...\n'
    '测试 主天线 中...\n')
_MESSAGE_PREPARE_AUX_ANTENNA = (
    'Make sure the aux WWAN antennta is connected to Port 1\n'
    'Make sure the aux WLAN antennta is connected to Port 2\n'
    'Then press key "K" to next stage.\n'
    '连接 副WWAN天线至 Port 1\n'
    '连接 副WLAN天线至 Port 2\n'
    '完成后按"K"键\n')
_MESSAGE_TEST_IN_PROGRESS_AUX = (
    'Testing AUX antenna...\n'
    '测试 副天线 中...\n')
_MESSAGE_WRITING_IN_PROGRESS = (
    'Writing log....\n'
    '记录中...\n')
_MESSAGE_RESULT_TAB = (
    'Results are listed below.\n'
    'Please disconnect the panel and press ENTER to write log.\n'
    '测试结果显示如下\n'
    '请将AB Panel移除, 并按ENTER完成测试\n')

_TEST_SN_NUMBER = 'TEST-SN-NUMBER'
_LABEL_SIZE = (300, 30)
TEMP_CACHES = '/tmp/VSWR.usb.data'

def make_status_row(row_name,
                    display_dict,
                    init_prompt=None,
                    init_status=None):
    """
    Returns a GTK HBox shows an status of a item.

    @param row_name: symbolic name of the item.
    @param display_dict: dict consists of the status.
    @param init_prompt: initial string for the row.
    @param init_status: initial status for the row.
    """
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
        """
        Callback to update prompt when parent object is displayed.

        @param widget: parent widget.
        @param event: wrapped GTK event, simply ignored in this callback.
        """
        prompt = display_dict[row_name]['prompt']
        widget.set_text(prompt)

    def status_label_expose(widget, event):
        """
        Callback to update status when parent object is displayed.

        @param widget: parent widget.
        @param event: wrapped GTK event, simply ignored in this callback.
        """
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
    """
    Returns a widget that displays the message and binds proper functions.

    @param message: Prompt string to display on the widget.
    @param on_key_continue: function that will be called when one of
        keys_to_continue is pressed.
    @param keys_to_continue: a list of keycodes that will trigger continuation.
    @param on_key_skip: function that will be called when one of keys_to_skip
        is pressed.
    @param keys_to_skip: a list of keycodes that will trigger skip.
    @param fg_color: the color of prompt.
    """
    if keys_to_skip is None:
        keys_to_skip = []

    widget = gtk.VBox()
    widget.add(ful.make_label(message, fg=fg_color))
    def key_release_callback(widget, event):
        """Callback for key pressed event.

        @param widget: parent widget.
        @param event: wrapped GTK event, including pressed key info.
        """
        if on_key_continue and event.keyval in keys_to_continue:
            on_key_continue()
            return True
        if on_key_skip and event.keyval in keys_to_skip:
            on_key_skip()
            return True

    widget.key_callback = key_release_callback
    return widget

def get_formatted_time():
    """Returns the current time in formatted string."""
    # Windows doesn't allowed : as a separtor. In addition,
    # we don't need information down to milliseconds actually.
    return TimeString(time_separator='-', milliseconds=False)

def get_formatted_date():
    return time.strftime("%Y%m%d", time.localtime())

def upload_to_shopfloor(file_path, log_name,
                        ignore_on_fail=False, timeout=10):
    """
    Attempts to upload arbitrary file to the shopfloor server.

    @param file_path: local file to upload.
    @param log_name: file_name that will be saved under shopfloor.
    @param ignore_on_fail: if exception will be raised when upload fails.
    @param timeout: maximal time allowed for getting shopfloor instance.
    """
    try:
        with open(file_path, 'r') as f:
            chunk = f.read()
        description = 'aux_logs (%s, %d bytes)' % (log_name, len(chunk))
        start_time = time.time()
        shopfloor_client = shopfloor.get_instance(
            detect=True, timeout=timeout)
        shopfloor_client.SaveAuxLog(log_name, Binary(chunk))
        logging.info(
            'Successfully synced %s in %.03f s',
            description, time.time() - start_time)
    except Exception as e:
        if ignore_on_fail:
            factory.console.info(
                'Failed to sync with shopfloor for [%s], ignored', log_name)
        else:
            raise e
    return True

class factory_Antenna(test.test):
    """
    This is a test for antenna module in a passive approach. Antenna under test
    will be located in another fixture and profiled by Agilent E5071C (ENA).

    An autotest usually running on a DUT and run only once. However, this test
    is designed to test antenna module repeatedly. Once the connection to ENA
    created, the state will loop infinitely to avoid additional setup wtih ENA
    for every single antenna (i.e. doesn't need to restart the autotest for
    each module)
    """
    version = 9

    # The state goes from _STATE_INITIAL to _STATE_RESULT_TAB then jumps back
    # to _STATE_PREPARE_PANEL for another testing cycle.
    _STATE_INITIAL = -1
    _STATE_SHOPFLOOR_DOWNLOAD = 0
    _STATE_WAIT_USB = 1
    _STATE_CONNECTING_ENA = 2
    _STATE_CALIBRATION_CHECK = 3
    _STATE_PREPARE_PANEL = 4
    _STATE_ENTERING_SN = 5
    _STATE_PREPARE_MAIN_ANTENNA = 6
    _STATE_TEST_IN_PROGRESS_MAIN = 7
    _STATE_PREPARE_AUX_ANTENNA = 8
    _STATE_TEST_IN_PROGRESS_AUX = 9
    _STATE_WRITING_IN_PROGRESS = 10
    _STATE_RESULT_TAB = 11

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
        """Adavnces the state(widget) to next assigned."""
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

    def setup_network(self):
        """
        Setups the network of local host.

        The network setting in config should look like example below:
        local_ip = ("192.168.132.66", "255.255.0.0")
        ena_mapping = {
            "192.168.132.114": {"MY46107777": "Taipei E5071C-1",
                                "MY99999999": "Taipei E5071C-mock"},
            "192.168.132.115": {"MY46107723": "Factory E5071C Line1",
                                "MY46107725": "Factory E5071C Line2"},
            "192.168.132.116": {"MY46107724": "Factory E5071C Line3",
                                "MY46107726": "Factory E5071C Line4"},
        """
        def _flush_route_cache():
            """Clears the local route cache."""
            Spawn(['ip', 'route', 'flush', 'cache'],
                  call=True, check_call=True)

        factory.console.info('Setup network...')
        _flush_route_cache()
        network_config = self.config['network']
        interface = FindUsableEthDevice(raise_exception=True)
        factory.console.info('Found Ethernet on %s' % interface)
        # If a local IP is required create an IP alias of wired interface
        local_ip = network_config['local_ip']
        if local_ip is not None:
            ip_address = local_ip[0]
            netmask = local_ip[1]
            alias_interface = interface + ":1"
            factory.console.info('Creating IP alias with %s/%s',
                                 ip_address, netmask)
            Spawn(['ifconfig', alias_interface, ip_address,
                   'netmask', netmask],
                  call=True, check_call=True)
            # Make sure the underlying interface is up
            Spawn(['ifconfig', interface, 'up'], call=True, check_call=True)
        else:
            alias_interface = interface

        # Add the route information to each of the possible ENA in
        # the mapping list. In addition, check if there are only one
        # ENA in the visible scope.
        ena_mapping = network_config['ena_mapping']
        valid_ping_count = 0
        for ena_ip in ena_mapping.iterkeys():
            # Manually add route information for all the possible ENA.
            # It might be duplicated, so ignore the exit code.
            Spawn(['route', 'add', ena_ip, alias_interface], call=True)
            # Clear the route cache just in case.
            _flush_route_cache()
            # Ping the host
            factory.console.info('Searching for IP: %s', ena_ip)
            if PingHost(ena_ip, 2) == 0:
                factory.console.info('Found IP %s in the network', ena_ip)
                valid_ping_count += 1
                self.ena_ip = ena_ip
        factory.console.info('Routing table information\n%r\n',
                             SpawnOutput(['route', '-n']))
        assert valid_ping_count == 1, (
                "Found %d ENA which should be only one" % valid_ping_count)
        factory.console.info('IP of ENA automatic detected as %s', self.ena_ip)

    def load_config(self, config_path):
        """
        Reads the configuration from a file.

        @param config_path: The location of config file.
        """
        self.config = self.base_config.Read(
                config_path, event_log=self._event_log)
        # Load the shopfloor related setting.
        self.path_name = self.config.get('path_name', 'UnknownPath')
        self.shopfloor_config = self.config.get('shopfloor', {})
        self.shopfloor_enabled = self.shopfloor_config.get('enabled', False)
        self.shopfloor_timeout = self.shopfloor_config.get('timeout')
        self.shopfloor_ignore_on_fail = (
                self.shopfloor_config.get('ignore_on_fail'))
        self.allowed_iteration = self.config.get('allowed_iteration', None)
        factory.console.info("Config loaded.")
        # Setup Network
        self.setup_network()

    def download_from_shopfloor(self):
        """Downloads parameters from shopfloor."""
        if self.load_from_shopfloor:
          caches_dir = os.path.join(CACHES_DIR, 'parameters')
          DownloadParameters([self.config_path], caches_dir)
          # Parse and load the parameters.
          self.load_config(os.path.join(caches_dir, self.config_path))
        self.advance_state()

    def on_usb_insert(self, dev_path):
        """
        Callback to load USB parameters when USB inserted.

        @param dev_path: the path where inserted USB presented in /dev
        """
        if self._state == self._STATE_WAIT_USB:
            self.dev_path = dev_path
            if not self.load_from_shopfloor:
              with MountedMedia(self.dev_path, 1) as config_dir:
                  config_path = os.path.join(config_dir, self.config_path)
                  self.load_config(config_path)
            factory.console.info("USB path located as %s", self.dev_path)
            self.advance_state()

    def on_usb_remove(self, dev_path):
        """
        Callback to prevent unexpected USB removal.

        @param dev_path: dummy argument from GTK event.
        """
        if self._state != self._STATE_WAIT_USB:
            raise error.TestNAError("USB removal is not allowed during test")

    def match_config(self, serial_number):
        """
        Based on the serial number, dynamically load coressponding settings.

        With this feature, we can utilize a single equipment as multiple
        stations. If serial_number doesn't match with any known config, the
        last config in configuration will be applied.

        @param serial_number: serial_number of incoming antenna module.
        """
        # Search if there is a config that matches
        config_matched = False
        for configs in self.config['serial_specific_configuration']:
            self.sn_regex = configs.get('sn_regex', None)
            assert self.sn_regex, "Regexp of SN must exist"
            self.current_config_name = configs.get('config_name', 'undefined')
            self.auto_screenshot = configs.get('auto_screenshot', False)
            self.reference_info = configs.get('reference_info', False)
            self.marker_info = configs.get('set_marker', None)
            self.vswr_threshold = configs.get('vswr_threshold', None)
            self.sweep_restore = configs.get('sweep_restore', None)
            factory.console.info('Matching SN[%s] with regex[%s]',
                                 serial_number, self.sn_regex)
            if re.search(self.sn_regex, serial_number):
                config_matched = True
                factory.console.info('Matching configuration - %s',
                            self.current_config_name)
                break
        if not config_matched:
            factory.console.info(
                    'No valid configuration matched with serial[%s],'
                    'use config[%s], sn_regexp[%s]',
                    serial_number, self.current_config_name, self.sn_regex)

    def register_callbacks(self, window):
        """
        Utility function to register event with GTK window.

        @param window: GTK window object.
        """
        def key_press_callback(widget, event):
            """
            Callback for invoking widget specific key handler.

            @param widget: parent widget.
            @param event: GTK event from parent object.
            """
            if hasattr(self, 'last_widget'):
                if hasattr(self.last_widget, 'key_callback'):
                    return self.last_widget.key_callback(widget, event)
            return False
        window.connect('key-press-event', key_press_callback)
        window.add_events(gtk.gdk.KEY_PRESS_MASK)

    def switch_widget(self, widget_to_display):
        """
        Switches the current widget to widget_to_display.

        @param widget_to_display: next widget to show.
        """
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
        """
        Callback for sn_input_widget for faking a serial_number.

        @param entry: the textbox in sn_input_widget.
        @param key: pressed key.
        """
        if key.keyval == gtk.keysyms.Tab:
            entry.set_text(_TEST_SN_NUMBER)
            return True
        return False

    def on_sn_complete(self, serial_number):
        """
        Callback for sn_input_widget when enter pressed.

        @param serial_number: serial_number of the antenna module.
        """
        self.serial_number = serial_number
        self.log_to_file.write('Serial_number : %s\n' % serial_number)
        self.log_to_file.write('Started at : %s\n' % datetime.datetime.now())
        # TODO(itspeter): display the SN info in the result tab.
        self._update_status('sn', self.check_sn_format(serial_number))
        self._event_log.Log('ab_panel_start',
                            path=self.path_name,
                            ab_serial_number=self.serial_number)
        self.advance_state()

    def check_sn_format(self, sn):
        """
        Checks if the serial_number matches pattern.

        It will first call match_config to determine configuration and then
        test if pattern matched with that configuration.

        @param sn: serial_number from sn_input_widget.
        """
        self.match_config(sn)
        regex_ret = re.search(self.sn_regex, sn)
        return True if regex_ret else False

    def write_to_usb_and_shopfloor(self, filename, content):
        """
        Saves detailed log into USB stick and shopfloor.

        @param filename: filename in USB stick.
        @param content: content to save.
        """
        with MountedMedia(self.dev_path, 1) as mount_dir:
            formatted_date = get_formatted_date()
            target_dir = os.path.join(
                    mount_dir, formatted_date, 'usb')
            TryMakeDirs(target_dir)
            full_path = os.path.join(target_dir, filename)
            with open(full_path, 'a') as f:
                f.write(content)
            factory.console.info("Log wrote with SN: %s.", self.serial_number)
            # Copy the file to a temporary position
            shutil.copyfile(full_path, TEMP_CACHES)
            factory.console.info("USB file[%s] copied to [%s]",
                                 full_path, TEMP_CACHES)

        # Upload to the shopfloor
        log_name = os.path.join(self.path_name, 'usb', filename)
        if self.shopfloor_enabled:
            factory.console.info("Sending logs to shopfloor")
            # Upload to shopfloor
            upload_to_shopfloor(
                    TEMP_CACHES,
                    log_name,
                    ignore_on_fail=self.shopfloor_ignore_on_fail,
                    timeout=self.shopfloor_timeout)
            factory.console.info("Log %s uploaded.", filename)

    def capture_screenshot(self, filename):
        """Captures the screenshot based on the setting.

        Timestamp will be automatically added as postfix.

        @param filename: primary filename.
        """
        if self.auto_screenshot:
            # Save a screenshot copy in ENA
            filename_with_timestamp = '%s[%s]' % (
                    filename, get_formatted_time())
            self.ena.SaveScreen(filename_with_timestamp)
            # Get another screenshot from the ENA's http server.
            # We use SaveScreen to store a local backup on the E5071C (windows).
            # Because the SCPI protocol doesn't provide a way to transmit binary
            # file. The trick here is to invoke the screenshot function via its
            # http service (image.asp) and get the saved file (it is always
            # disp.png)
            factory.console.info("Requesting ENA to generate screenshot")
            urlopen("http://%s/image.asp" % self.ena_ip).read()
            png_content = urlopen("http://%s/disp.png" % self.ena_ip).read()
            self._event_log.Log('vswr_screenshot',
                                ab_serial_number=self.serial_number,
                                path=self.path_name,
                                filename=filename_with_timestamp)

            formatted_date = get_formatted_date()
            factory.console.info("Saving screenshot to USB under dates %s",
                                 formatted_date)
            with MountedMedia(self.dev_path, 1) as mount_dir:
                target_dir = os.path.join(
                        mount_dir, formatted_date, 'screenshot')
                TryMakeDirs(target_dir)
                filename_in_abspath = os.path.join(
                        target_dir,  filename_with_timestamp)
                with open(filename_in_abspath, 'a') as f:
                    f.write(png_content)
                factory.console.info("Screenshot %s saved in USB.",
                                     filename_with_timestamp)
                # Copy the file to a temporary position
                shutil.copyfile(filename_in_abspath, TEMP_CACHES)
                factory.console.info("USB file[%s] copied to [%s]",
                                     filename_in_abspath, TEMP_CACHES)

            if self.shopfloor_enabled:
                factory.console.info("Sending screenshot to shopfloor")
                log_name = os.path.join(
                        self.path_name, 'screenshot', filename_with_timestamp)
                # Upload to shopfloor
                upload_to_shopfloor(
                        TEMP_CACHES,
                        log_name,
                        ignore_on_fail=self.shopfloor_ignore_on_fail,
                        timeout=self.shopfloor_timeout)
                factory.console.info("Screenshot %s uploaded.",
                                     filename_with_timestamp)

    def restore_sweep(self):
        """Restores to a specific linear sweeping."""
        if self.sweep_restore:
            self.ena.SetLinearSweep(
                self.sweep_restore[0], self.sweep_restore[1])

    def set_marker(self):
        for channel, marker_num, freq in self.marker_info:
            self.ena.SetMarker(channel, marker_num, freq)

    def test_main_antennas(self):
        """Tests the main antenna of cellular and wifi."""
        freqs = set()
        self._add_required_freqs('cell', freqs)
        self._add_required_freqs('wifi', freqs)
        ret = self._get_traces(freqs, ['S11', 'S22'],
                               purpose='test_main_antennas')
        self.restore_sweep()
        self.set_marker()
        self.capture_screenshot('[%s]%s' % ('MAIN', self.serial_number))
        self._test_main_cell_antennas(ret)
        self._test_main_wifi_antennas(ret)
        self.advance_state()

    def test_aux_antennas(self):
        """Tests the aux antenna of cellular and wifi."""
        freqs = set()
        self._add_required_freqs('cell', freqs)
        self._add_required_freqs('wifi', freqs)
        ret = self._get_traces(freqs, ['S11', 'S22'],
                               purpose='test_aux_antennas')
        self.restore_sweep()
        self.set_marker()
        self.capture_screenshot('[%s]%s' % ('AUX', self.serial_number))
        self._test_aux_cell_antennas(ret)
        self._test_aux_wifi_antennas(ret)
        self.generate_final_result()

    def _update_status(self, row_name, result):
        """
        Updates status of different items.

        @param row_name: the symbolic name of item.
        @param result: the result of item.
        """
        result_map = {
            True: ful.PASSED,
            False: ful.FAILED,
            None: ful.UNTESTED
        }
        assert result in result_map, "Unknown result"
        self.display_dict[row_name]['status'] = result_map[result]

    def _test_main_cell_antennas(self, traces):
        """
        Verifies the trace obtained meets the threshold for main cell antenna.

        @param traces: traces from the equipment.
        """
        self._update_status(
            'cell_main',
            self._compare_traces(traces, 'cell', 1, 'cell_main', 'S11'))

    def _test_main_wifi_antennas(self, traces):
        """
        Verifies the trace obtained meets the threshold for wifi main antenna.

        @param traces: traces from the equipment.
        """
        self._update_status(
            'wifi_main',
            self._compare_traces(traces, 'wifi', 1, 'wifi_main', 'S22'))

    def _test_aux_cell_antennas(self, traces):
        """
        Verifies the trace obtained meets the threshold for aux cell antenna.

        @param traces: traces from the equipment.
        """
        self._update_status(
            'cell_aux',
            self._compare_traces(traces, 'cell', 3, 'cell_aux', 'S11'))

    def _test_aux_wifi_antennas(self, traces):
        """
        Verifies the trace obtained meets the threshold for aux wifi antenna.

        @param traces: traces from the equipment.
        """
        self._update_status(
            'wifi_aux',
            self._compare_traces(traces, 'wifi', 3, 'wifi_aux', 'S22'))

    def generate_final_result(self):
        """Generates the final result and saves logs."""
        self._result = all(
           ful.PASSED == self.display_dict[var]['status']
           for var in self._RESULTS_TO_CHECK)
        self._update_status('result', self._result)
        self.log_to_file.write("Result in summary:\n%s\n" %
                               pprint.pformat(self.display_dict))
        self._event_log.Log('vswr_result',
                            ab_serial_number=self.serial_number,
                            path=self.path_name,
                            results=self.display_dict)
        # Save logs and hint user it is writing in progress.
        self.advance_state()

    def save_log(self):
        """Saves the logs and writes eventlog."""
        # TODO(itspeter): Dump more details upon RF teams' request.
        self.log_to_file.write("\n\nRaw traces:\n%s\n" %
                               pprint.pformat(self._raw_traces))
        self._event_log.Log('vswr_detail',
                            ab_serial_number=self.serial_number,
                            path=self.path_name,
                            raw_trace=self._raw_traces)
        self._event_log.Log('ab_panel_end',
                            ab_serial_number=self.serial_number,
                            path=self.path_name,
                            results=self.display_dict)
        try:
            self.write_to_usb_and_shopfloor(
                    self.serial_number + ".txt",
                    self.log_to_file.getvalue())
        except Exception as e:
            raise error.TestNAError(
                "Unable to save current log to USB stick - %s" % e)

        # Switch to the result widget
        self.advance_state()

    def _add_required_freqs(self, antenna_type, freqs_set):
        """
        Reads the required frequencies and add them to freqs_set.

        Format of antenna.params:
            {'vswr_threshold': {
              antenna_type: [
                (freq,
                  (main_min, main_max),
                  (coupling_min, coupling_max),
                  (aux_min, aux_max)), ...
        For example:
            {'vswr_threshold': {
              'cell': [
                (746,
                  (None, -6), (-50, None), (-15, -6)), ...

        Usage example:
            self._add_required_freqs('cell', freqs)

        @param antenna_type: antenna_type.
        @param freqs_set: the freqs_set that will be modified.
        """
        for config_tuple in self.vswr_threshold[antenna_type]:
            freqs_set.add(config_tuple[0])

    def _get_traces(self, freqs_set, parameters, purpose="unspecified"):
        """
        This function is a wrapper for GetTraces in order to log details.

        @param freqs_set: the set of frequency to acquire.
        @param parameters: the type of trace to acquire, for example, 'S11'
          'S22' ..etc. Detailed in GetTraces()
        @param purpose: additional tag for detailed logging.
        """
        # Generate the sweep tuples.
        freqs = sorted(freqs_set)
        segments = [(freq_min * 1e6, freq_max * 1e6, 2) for
                    freq_min, freq_max in
                    zip(freqs, freqs[1:])]

        self.ena.SetSweepSegments(segments)
        ret = self.ena.GetTraces(parameters)
        self._raw_traces[purpose] = ret
        return ret

    def check_measurement(self, standard_tuple, extracted_value,
                          print_on_failure=False, freq=None, title=None):
        """
        Compares whether the measurement meets the spec at single frequency.

        Failure details are also recorded in the eventlog. Console display is
        controlled by print_on_failure.

        @param standard_tuple: the pre-defined threshold.
        @param extracted_value: the value acquired from the trace.
        @param print_on_failure: If print_on_failure is enabled, details
          of failure band will be displayed under console.
        @param freq: frequency to display when print_on_failure is enabled.
        @param title: title to display when print_on_failure is enabled,
          usually is one of the 'cell_main', 'cell_aux', 'wifi_main',
          'wifi_aux'.
        """
        min_value = standard_tuple[0]
        max_value = standard_tuple[1]
        # Compare the minimum
        difference = (min_value - extracted_value) if min_value else 0
        difference = max(difference,
                         (extracted_value - max_value) if max_value else 0)
        result = True

        if difference > 0:
            # Hightlight the failed freqs in console.
            if print_on_failure:
                factory.console.info(
                        "%10s failed at %5s MHz[%9.3f dB], %9.3f dB "
                        "away from threshold[%s, %s]",
                        title, freq / 1000000.0, float(extracted_value),
                        float(difference), min_value, max_value)
            result = False
        # Record the detail for event_log
        self.vswr_detail_results.append(
            (title, freq / 1000000.0, float(extracted_value), result,
             float(difference), min_value, max_value))
        return result

    def _compare_traces(self, traces, antenna_type, column,
                        log_title, ena_parameter):
        """
        Compares whether returned traces and spec are aligned.

        It calls the check_measurement for each frequency and records
        coressponding result in eventlog and raw logs.

        Usage example:
            self._test_sweep_segment(traces, 'cell', 1, 'cell_main', 'S11')

        @param traces: Trace information from ENA.
        @param antenna_type: antenna_type, 'cell' or 'main'
        @param column: the coressponding column index to use as a threshold.
          As defined in _add_required_freqs 0 refers to (main_min, main_max),
          1 refers to (coupling_min, coupling_max), 2 refers to
          (aux_min, aux_max).
        @param log_title: title for the trace, usually is one of the
          'cell_main', 'cell_aux', 'wifi_main', 'wifi_aux'.
        @param ena_parameter: the type of trace to acquire, for example, 'S11'
          'S22' ..etc. Detailed in ena.GetTraces()
        """
        self.log_to_file.write(
            "Start measurement [%s], with profile[%s,col %s], from ENA-%s\n" %
            (log_title, antenna_type, column, ena_parameter))
        # Generate the sweep tuples.
        freqs = [atuple[0] * 1e6 for atuple in
                 self.vswr_threshold[antenna_type]]
        standards = [atuple[column] for atuple in
                     self.vswr_threshold[antenna_type]]
        freqs_responses = [traces.GetFreqResponse(freq, ena_parameter) for
                           freq in freqs]
        results = [self.check_measurement(
                std_range, ext_val, print_on_failure=True,
                freq=freq, title=log_title) for
                   freq, std_range, ext_val in
                   zip(freqs, standards, freqs_responses)]
        logs = zip(freqs, standards, freqs_responses, results)
        logs.insert(0, ("Frequency",
                        "Column-%s" % column,
                        "ENA-%s" % ena_parameter,
                        "Result"))
        self.log_to_file.write("%s results:\n%s\n" %
                               (log_title, pprint.pformat(logs)))
        self._event_log.Log(
            'vswr_measurement',
            ab_serial_number=self.serial_number,
            config=(log_title, antenna_type, column, ena_parameter),
            vswr_detail_results=self.vswr_detail_results,
            logs=logs)

        return all(results)

    def connect_ena(self):
        """Connnects to E5071C(ENA) , initialize the SCPI object."""
        # TODO(itspeter): Prepare IP address specifically for ENA
        # Setup the ENA host.
        factory.console.info('Connecting to the ENA...')
        self.ena = ENASCPI(self.ena_ip)
        # Check and report if this is an expected ENA.
        ena_sn = self.ena.GetSerialNumber()
        factory.console.info('Connected with ENA SN = %s.', ena_sn)
        # Check if this serial number is in the white list.
        ena_whitelist = self.config['network']['ena_mapping'][self.ena_ip]
        if ena_sn not in ena_whitelist:
            self.ena.Close()
            raise ValueError(
                    'ENA with SN:%s is not in the while list' % ena_sn)
        self.ena_name = ena_whitelist[ena_sn]
        factory.console.info('This ENA is now identified as %r', self.ena_name)
        self.advance_state()

    def check_calibration(self):
        """Checks if the Trace are flat as expected.

        A calibration_check config consist of a span and threshold.
        For example, the following tuple represents a check
            ((800*1E6, 6000*1E6, 100), (-0.3, 0.3))
        from 800 MHz to 6GHz, sampling 100 points and require the value to
        stay with in (-0.3, 0.3).
        """
        calibration_check = self.config.get('calibration_check', None)
        if calibration_check is not None:
            start_freq, stop_freq, sample_points = calibration_check[0]
            calibration_threshold = calibration_check[1]
            factory.console.info(
                    'Checking calibration status from %.2f to %.2f, '
                    'with threshold (%f, %f)', start_freq, stop_freq,
                    calibration_threshold[0], calibration_threshold[1])
            self.ena.SetSweepSegments([(start_freq, stop_freq, sample_points)])
            traces_to_check = ['S11', 'S22']
            ret = self.ena.GetTraces(traces_to_check)
            overall_result = True
            for trace in traces_to_check:
                for idx, freq in enumerate(ret.x_axis):
                    single_result = CheckPower(
                        '%s-%15.2f' % (trace,freq),
                        ret.traces[trace][idx],
                        calibration_threshold, list())
                    if not single_result:
                        # Still continue to prompt user where are failing.
                        overall_result = False
            if overall_result:
                factory.console.info('Basic calibration check passed.')
            else:
                raise error.TestNAError("Calibration check failed.")
        self.advance_state()

    def reset_data_for_next_test(self):
        """
        Resets internal data for the next testing cycle.

        prepare_panel_widget is the first widget of a new testing cycle. This
        function resets all the testing data. Caller should call switch_widget
        to change current UI to the first widget.
        """
        self.log_to_file = StringIO.StringIO()
        self._raw_traces = {}
        self.vswr_detail_results = []
        self.sn_input_widget.get_entry().set_text('')
        for var in self._STATUS_NAMES:
            self._update_status(var, None)
        factory.console.info("Reset internal data.")

    def on_result_enter(self):
        """Callback wrapper for key pressed in result_widget."""
        self.current_iteration += 1
        factory.console.info('The %5d-th panel test is finished.',
                             self.current_iteration)
        # Check the allowed_iteration
        if self.allowed_iteration is not None:
            if self.current_iteration >= self.allowed_iteration:
                factory.console.info(
                    'This test have to restart after %d iterations, '
                    'which is reached.', self.allowed_iteration)
                gtk.main_quit()
        self.advance_state()
        return True

    def switch_to_sn_input_widget(self):
        """Callback wrapper for key pressed in prepare_panel_widget."""
        self.advance_state()
        return True

    def make_result_widget(self, on_key_enter):
        """Returns a widget that displays test result.

        @param on_key_enter: callback function when enter pressed.
        """
        widget = gtk.VBox()
        widget.add(ful.make_label(_MESSAGE_RESULT_TAB))
        for name, label in zip(self._STATUS_NAMES, self._STATUS_LABELS):
            widget.add(make_status_row(name, self.display_dict,
                                       label, ful.UNTESTED))
        def key_press_callback(widget, event):
            """Callback wrapper for handle key pressed event.

            @param widget: parent widget.
            @param event: wrapped GTK event, including pressed key info.
            """
            if event.keyval == gtk.keysyms.Return:
                on_key_enter()

        widget.key_callback = key_press_callback
        return widget

    def run_once(self, config_path, timezone,
                 load_from_shopfloor=True):
        """
        Main entrance for the test.

        @param config_path: configuration path from the root of USB disk or
            shopfloor parameters.
        @param timezone: the timezone might be different from shopfloor.
            use this argument to set proper timezone in fixture host if
            necessary.
        @param load_from_shopfloor: Whether to load parameters from shopfloor.
        """
        factory.console.info('%s run_once', self.__class__)
        factory.console.info(
            '(config_path: %s, timezone: %s, load_from_shopfloor: %s)',
            config_path, timezone, load_from_shopfloor)
        self.config_path = config_path
        self.ena = None       # It will later be assigned when connected
        self.ena_ip = None    # It will later be assigned when config loaded
        self.ena_name = None  # It will later be assigned when connected
        self.dev_path = None  # It will later be assigned when USB plug-in
        self.allowed_iteration = None  # It will later be assigned
        self.current_iteration = 0     # The number of panel tested.
        self.load_from_shopfloor = load_from_shopfloor

        # Setup the timezone
        os.environ['TZ'] = timezone
        # Initial EventLog
        self._event_log = EventLog.ForAutoTest()

        # Initialize variables.
        self.display_dict = {}
        self.base_config = PluggableConfig({})
        self.last_handler = None
        # Set up the UI widgets.
        self.usb_prompt_widget = gtk.VBox()
        if self.load_from_shopfloor:
            self.usb_prompt_widget.add(
                    ful.make_label(_MESSAGE_USB_LOG_STORAGE))
        else:
            self.usb_prompt_widget.add(
                    ful.make_label(_MESSAGE_USB_LOAD_PARAMETERS))

        self.shopfloor_download_widget = gtk.VBox()
        self.shopfloor_download_widget.add(
                ful.make_label(_MESSAGE_SHOPFLOOR_DOWNLOAD))

        self.connecting_ena_widget = gtk.VBox()
        self.connecting_ena_widget.add(ful.make_label(_MESSAGE_CONNECTING_ENA))

        self.calibration_check_widget = gtk.VBox()
        self.calibration_check_widget.add(
            ful.make_label(_MESSAGE_CALIBRATION_CHECK))

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
            self._STATE_SHOPFLOOR_DOWNLOAD:
                (self.shopfloor_download_widget, self.download_from_shopfloor),
            self._STATE_WAIT_USB:
                (self.usb_prompt_widget, None),
            self._STATE_CONNECTING_ENA:
                (self.connecting_ena_widget, self.connect_ena),
            self._STATE_CALIBRATION_CHECK:
                (self.calibration_check_widget, self.check_calibration),
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
