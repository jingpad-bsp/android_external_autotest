# Copyright (c) 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, string, time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import crash_detector
from autotest_lib.client.common_lib.cros import power_cycle_usb_util
from autotest_lib.server import autotest, test

_WAIT_DELAY = 10

class platform_CFM_USBPeripheralStress(test.test):
    """USB Peripheral Stress Test - HotPlug Stress & Reboot Stress"""
    version = 1


    def action_login(self):
        """Login i.e. runs using client test

        @exception TestFail failed to login within timeout.

        """
        self.autotest_client.run_test(self.client_autotest,
                                      exit_without_logout=True)


    def hot_plug_check_peripheral(self):
        """Power cycles USB port on which peripheral is connected."""

        for peripheral_name, vid_pid in self.peripheral_dict.iteritems():
            self.peripheral_name = peripheral_name
            self.vid, self.pid = vid_pid
            try:
                power_cycle_usb_util.power_cycle_usb_vidpid(self.host,
                        self.board, self.vid, self.pid)
                time.sleep(_WAIT_DELAY)
            except KeyError:
                raise error.TestFail('Couldn\'t find target device: '
                                     'vid:pid {}:{}'.format(self.vid, self.pid))
            self.check_usb_enumeration(peripheral_name=self.peripheral_name,
                                       vendor_id=self.vid)


    def check_usb_enumeration(self, peripheral_name, vendor_id):
        """Gets usb device type info from lsusb output based on vendor id to
           check if usb device is enumerated.

        @peripheral_name: USB Peripheral
        @vendor_id: Device vendor id.

        """
        try:
            cmd = 'lsusb -v -d ' + vendor_id + ': | grep iProduct'
            cmd_out = self.host.run(cmd, ignore_status=False).stdout.strip()
            if cmd_out is not None:

                # cmd_out[8:] trims the first 8 characters from the returned
                # string which is "iProduct" and displays peripheral name.
                logging.info('USB Peripheral {} enumerated successfully'
                             .format(string.strip(cmd_out[8:])))
        except Exception as e:
            raise error.TestFail('Couldn\'t find Plugged {} with: vid:'
                    '{} '.format(peripheral_name, vendor_id))

    def upload_crash_count(self, count):
        """Uploads crash count based on length of crash_files list."""
        self.output_perf_value(description='number_of_crashes',
                               value=int(count),
                               units='count', higher_is_better=False)

    def cleanup(self):
        """Reboot host"""
        self.host.reboot()


    def run_once(self, host, client_autotest, repeat, action_sequence,
                 peripheral_dict, crash_check=False):
        """Main function to run autotest.

        @param host: Host object representing the DUT.
        @client_autotest: Client side test to run on host for login action.
        @repeat: Number of times "actions" to repeat for stress testing.
        @action_sequence: Sequence of actions to perform during test run.
        @peripheral_dict: Contains USB peripheral's vid, pid under test.
        @crash_check: True to check for crashes, False otherwise.

        """
        self.host = host
        self.board = host.get_board().split(':')[1]

        if not self.board == 'guado':
            logging.info("Skipping test, this test only runs on Guado")
            return

        self.client_autotest = client_autotest

        # Login on host, so that Chrome sees all USB Peripherals.
        self.autotest_client = autotest.Autotest(self.host)

        self.crash_check = crash_check
        self.login_status = False
        self.peripheral_dict = peripheral_dict
        self.action_login()
        self.login_status = True
        self.action_step = None
        action_sequence = action_sequence.upper()
        actions = action_sequence.split(',')

        if crash_check:
            self.detect_crash = crash_detector.CrashDetector(self.host)
            self.detect_crash.remove_crash_files()

        # Unplug, plug, check usb peripheral and leave plugged.
        self.hot_plug_check_peripheral()

        for iteration in xrange(1, repeat + 1):
            step = 0
            for action in actions:
                step += 1
                action = action.strip()
                self.action_step = 'STEP %d.%d. %s' % (iteration, step, action)
                logging.info(self.action_step)

                if action.startswith('LOGIN'):
                    if self.login_status:
                        logging.debug('Skipping login. Already logged in.')
                        continue
                    else:
                        self.action_login()
                        self.login_status = True
                    for peripheral_name, vid_pid in self.peripheral_dict.iteritems():
                        self.peripheral_name = peripheral_name
                        self.vid, self.pid = vid_pid
                        self.check_usb_enumeration(self.peripheral_name,
                                                   vendor_id=self.vid)

                elif action == 'REBOOT':
                    self.host.reboot()
                    time.sleep(_WAIT_DELAY)
                    self.login_status = False

                elif action == 'HOTPLUG':
                    self.hot_plug_check_peripheral()

                else:
                    logging.info('WRONG ACTION: %s .', self.action_step)

        # Uploads crash count that occurred during test run.
        self.upload_crash_count(len(self.detect_crash.get_crash_files()))
