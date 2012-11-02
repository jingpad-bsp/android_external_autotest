# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json, logging, time

from autotest_lib.server import autotest, test
from autotest_lib.server.cros import stress
from autotest_lib.client.common_lib import error

_WAIT_DELAY = 5


class platform_ExternalUSBStress(test.test):
    """Uses servo to repeatedly connect/remove USB devices."""
    version = 1


    def run_once(self, host, client_autotest):
        autotest_client = autotest.Autotest(host)
        diff_list = []
        off_list = []

        def loggedin():
            """
            Checks if the host has a logged in user.

            @return True if a user is logged in on the device.
            """
            try:
                cmd_out = host.run('cryptohome --action=status').stdout.strip()
            except:
                return False
            status = json.loads(cmd_out)
            return any((mount['mounted'] for mount in status['mounts']))


        def strip_lsusb_output(lsusb_output):
            items = lsusb_output.split('\n')
            named_list = []
            for item in items:
              columns = item.split(' ')
              name = ' '.join(columns[6:len(columns)])
              named_list.append(name)
            return named_list


        def set_hub_power(on=True):
            reset = 'off'
            if not on:
                reset = 'on'
            host.servo.set('dut_hub1_rst1', reset)
            time.sleep(_WAIT_DELAY)
            return strip_lsusb_output(host.run('lsusb').stdout.strip())


        def test_suspend(remove_while_suspended=False):
            set_hub_power(True)
            host.servo.lid_close()
            time.sleep(_WAIT_DELAY)
            if remove_while_suspended:
                set_hub_power(False)
            host.servo.lid_open()
            time.sleep(_WAIT_DELAY)
            connected = strip_lsusb_output(host.run('lsusb').stdout.strip())
            if remove_while_suspended:
                if connected != off_list:
                    raise error.TestFail('Devices were not removed on wake.')
                return
            if not diff_list.issubset(connected):
                raise error.TestFail('The list of connected items does not '
                                     'match the master list.\nMaster: %s\n'
                                     'Current: %s' % (diff_list, connected))


        def test_hotplug():
            # Testing hot plug so re-generate the off_list for this test
            removed = set_hub_power(False)
            connected = set_hub_power(True)
            if not diff_list.issubset(connected):
                raise error.TestFail('The list of connected items does not '
                                     'match the master list.\nMaster: %s\n'
                                     'Current: %s' % (diff_list, connected))

        def stress_external_usb():
            if not loggedin():
                return

            #test_suspend(remove_while_suspended=True)
            test_hotplug()
            test_suspend()


        host.servo.enable_usb_hub()
        host.servo.set('usb_mux_sel3', 'dut_sees_usbkey')

        connected = set_hub_power(True)
        off_list = set_hub_power(False)
        diff_list = set(connected).difference(set(off_list))
        logging.info('Connected devices list: %s' % diff_list)
        set_hub_power(True)

        stressor = stress.ControlledStressor(stress_external_usb)
        stressor.start(start_condition=loggedin)
        autotest_client.run_test(client_autotest)
        stressor.stop()
