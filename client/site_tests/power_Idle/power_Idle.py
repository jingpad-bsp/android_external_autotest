# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import service_stopper
from autotest_lib.client.cros.bluetooth import bluetooth_device_xmlrpc_server
from autotest_lib.client.cros.power import power_test


class power_Idle(power_test.power_Test):
    """class for power_Idle test.

    Collects power stats when machine is idle, also compares power stats between
    when bluetooth adapter is on and off.
    """
    version = 1

    def initialize(self):
        super(power_Idle, self).initialize(seconds_period=10.)

    def run_once(self, idle_time=120, bt_warmup_time=20):
        """Collect power stats when bluetooth adapter is on or off.

        """
        with chrome.Chrome():
            self.start_measurements()
            time.sleep(idle_time)
            self.checkpoint_measurements('bluetooth_adapter_off')

            # Turn on bluetooth adapter.
            bt_device = bluetooth_device_xmlrpc_server \
                    .BluetoothDeviceXmlRpcDelegate()
            # If we cannot start bluetoothd, fail gracefully and still write
            # data with bluetooth adapter off to file, as we are interested in
            # just that data too. start_bluetoothd() already logs the error so
            # not logging any error here.
            if not bt_device.start_bluetoothd():
                return
            if not bt_device.set_powered(True):
                logging.warning("Cannot turn on bluetooth adapter.")
                return
            time.sleep(bt_warmup_time)
            if not bt_device._is_powered_on():
                logging.warning("Bluetooth adapter is off.")
                return
            t1 = time.time()
            time.sleep(idle_time)
            self.checkpoint_measurements('bluetooth_adapter_on', t1)
            bt_device.set_powered(False)
            bt_device.stop_bluetoothd()
