# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json, logging, re, time

from autotest_lib.server import autotest, test
from autotest_lib.server.cros import stress
from autotest_lib.client.common_lib import error

_WAIT_DELAY = 5
_REQUEST_SUSPEND_CMD = ('/usr/bin/dbus-send --system / '
                        'org.chromium.PowerManager.RequestSuspend')

class platform_ExternalUSBStress(test.test):
    """Uses servo to repeatedly connect/remove USB devices."""
    version = 1
    use_servo_for_suspend = True

    def run_once(self, host, client_autotest, suspends, network_debug):
        autotest_client = autotest.Autotest(host)
        diff_list = []
        off_list = []
        # The servo hubs come up as diffs in connected components.  These
        # should be ignored for this test.  It is a list so when servo next
        # is available it may have a differnet hub which can be appended.
        servo_hardware_list = ['Standard Microsystems Corp.']
        client_termination_file_path = '/tmp/simple_login_exit'

        def logged_in():
            """
            Checks if the host has a logged in user.

            @return True if a user is logged in on the device.
            """
            try:
                out = host.run('cryptohome --action=status').stdout.strip()
            except:
                return False
            try:
                status = json.loads(out)
            except ValueError:
                logging.info('Cryptohome did not return a value, retrying.')
                return False

            return any((mount['mounted'] for mount in status['mounts']))


        def strip_lsusb_output(lsusb_output):
            items = lsusb_output.split('\n')
            named_list = []
            unnamed_device_count = 0
            for item in items:
                columns = item.split(' ')
                if len(columns) == 6:
                    logging.info('Unnamed device located, adding generic name.')
                    name = 'Unnamed device %d' % unnamed_device_count
                    unnamed_device_count += 1
                else:
                    name = ' '.join(columns[6:]).strip()
                if name not in servo_hardware_list:
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

            if self.use_servo_for_suspend:
                host.servo.lid_close()
            else:
                host.run(_REQUEST_SUSPEND_CMD)

            time.sleep(_WAIT_DELAY)
            if remove_while_suspended:
                set_hub_power(False)

            if self.use_servo_for_suspend:
                host.servo.lid_open()
            else:
                host.servo.power_normal_press()

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


        def exit_client():
            host.run('touch %s' % client_termination_file_path)


        def stress_external_usb():
            if not logged_in():
                return

            # Cannot run this test, blocked on https://crosbug.com/p/16310
            # test_suspend(remove_while_suspended=True)
            test_hotplug()
            test_suspend()


        if network_debug:
            logging.info('Network debugging enabled.')
            host.run('ff_debug +dhcp')
            host.run('ff_debug --level -2')

        lsb_release = host.run('cat /etc/lsb-release').stdout.split('\n')
        for line in lsb_release:
            m = re.match(r'^CHROMEOS_RELEASE_BOARD=(.+)$', line)
            # The Daisy EC does not support lid close,
            # see http://crosbug.com/p/16369.
            if m and m.group(1) == 'daisy':
                self.use_servo_for_suspend = False
                logging.info('Not using servo for suspend because board %s '
                             'is not supported.' % m.group(1))

        host.servo.switch_usbkey('dut')
        host.servo.set('usb_mux_sel3', 'dut_sees_usbkey')

        # There are some mice that need the data and power connection to both
        # be removed, otherwise they won't come back up.  This means that the
        # external devices should only use the usb connections labeled:
        # USB_KEY and DUT_HUB1_USB.
        connected = set_hub_power(True)
        off_list = set_hub_power(False)
        diff_list = set(connected).difference(set(off_list))
        if len(diff_list) == 0:
            raise error.TestError('No connected devices were detected.  Make '
                                  'sure the devices are connected to USB_KEY '
                                  'and DUT_HUB1_USB on the servo board.')
        logging.info('Connected devices list: %s' % diff_list)
        set_hub_power(True)

        stressor = stress.CountedStressor(stress_external_usb,
                                          on_exit=exit_client)
        stressor.start(suspends, start_condition=logged_in)
        autotest_client.run_test(client_autotest)
        stressor.wait()
