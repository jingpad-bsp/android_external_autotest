# -*- coding: utf-8 -*-
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory.event_log import EventLog
from autotest_lib.client.cros.factory.test_ui import UI

_HTML = '''
<h1>LAN & Bluetooth MAC address probing</h1><br>
<h2>%s</h2><br>
<h2>%s</h2><br>
<input type="button" value="Finished"
  onClick="test.pass()">
'''

LAN_MAC_PATH = "/sys/class/net/%s/address"
BT_MAC_PATH = "/sys/class/bluetooth/%s/address"

class factory_ProbeWifi(test.test):
    version = 1

    def run_once(self, lan_device='wlan0', bt_device='hci0', display=False):
        event_log = EventLog.ForAutoTest()
        self.ui = UI()
        lan_mac = bt_mac = ''

        if lan_device:
            path = LAN_MAC_PATH % lan_device
            if os.path.exists(path):
                lan_mac = 'LAN[%s](網路) MAC address: [%s]' % (
                    lan_device, open(path).read().strip())
            else:
                raise error.TestFail(
                    'LAN device %s does not exist' % lan_device)
            factory.console.info(lan_mac)
            event_log.Log('lan_mac', mac=lan_mac)

        if bt_device:
            path = BT_MAC_PATH % bt_device
            if os.path.exists(path):
                bt_mac = 'Bluetooth[%s](藍芽) MAC address: [%s]' % (
                    bt_device, open(path).read().strip())
            else:
                raise error.TestFail(
                    'Bluetooth device %s does not exist' % bt_device)
            factory.console.info(bt_mac)
            event_log.Log('bluetooth_mac', mac=bt_mac)

        if display:
            self.ui.set_html(_HTML % (lan_mac, bt_mac))
            self.ui.run()
