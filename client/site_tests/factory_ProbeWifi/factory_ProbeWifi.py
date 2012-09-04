# -*- coding: utf-8 -*-
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory_setup_modules
from cros.factory.test import factory
from cros.factory.event_log import EventLog
from cros.factory.test.test_ui import UI

_HTML_PREFIX = '''
<h1>LAN & Bluetooth MAC address probing</h1><br>
'''
_HTML_POSTFIX = '''
<input type="button" value="Finished"
  onClick="test.pass()">
'''

LAN_MAC_PATH = "/sys/class/net/%s/address"
BT_MAC_PATH = "/sys/class/bluetooth/%s/address"

class factory_ProbeWifi(test.test):
    version = 2

    def probe_devices(self, probe_list):
        '''Probe devices' MAC address.

        Args:
            probe_list: A list of tuples in the format:
            (type recorded in eventlog,
             device path,
             label to display in English,
             label to display in Chinese)
        '''
        display_strings = []
        for mac_type, device_path, label_en, label_zh in probe_list:
             if os.path.exists(device_path):
                 mac = open(device_path).read().strip()
                 display_strings.append(u'Mac address of %s(%s): %s' % (
                     label_en, label_zh, mac))
             else:
                 raise error.TestFail(
                     '%s device %s does not exist' % (mac_type, device_path))

             factory.console.info(display_str)
             self.event_log.Log('mac', mac_type=mac_type, mac=mac)
        return display_strings

    def run_once(self, lan_device='wlan0', bt_device='hci0', display=False):
        self.event_log = EventLog.ForAutoTest()
        self.ui = UI()
        probe_list = []
        if lan_device:
            probe_list.append(('lan',
                               LAN_MAC_PATH % lan_device,
                               u'LAN', u'網路'))

        if bt_device:
            probe_list.append(('bt',
                               BT_MAC_PATH % bt_device,
                               u'Bluetooth', u'藍芽'))

        display_strings = tuple(self.probe_devices(probe_list))
        factory.log(display_strings)
        if display:
            html = _HTML_PREFIX
            for display_string in display_strings:
                html += "<h2>%s</h2><br>" % display_string
            self.ui.SetHTML(html + _HTML_POSTFIX)
            self.ui.Run()
