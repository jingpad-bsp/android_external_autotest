# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time
import random

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.cfm import cfm_base_test
from autotest_lib.client.common_lib.cros import get_usb_devices
from autotest_lib.client.common_lib.cros import power_cycle_usb_util


LONG_TIMEOUT = 20
SHORT_TIMEOUT = 5
MIMO_VID = '17e9'
MIMO_PID = '016b'


class enterprise_CFM_MimoSanity(cfm_base_test.CfmBaseTest):
    """Tests the following fuctionality works on CFM enrolled devices:
           1. Verify CfM has Camera, Speaker and Mimo connected.
           2. Verify all peripherals have expected usb interfaces.
           3. Verify after rebooting CfM Mimo is present.
           4. Verify after powercycle Mimo Mimo comes back.
    """
    version = 1


    def _cmd_usb_devices(self):
        """
        Run linux cmd usb-devices
        @returns the output of "usb-devices" as string
        """
        usb_devices = (self._host.run('usb-devices', ignore_status=True).
                                         stdout.strip().split('\n\n'))
        usb_data = get_usb_devices._extract_usb_data(
                   '\nUSB-Device\n'+'\nUSB-Device\n'.join(usb_devices))
        return usb_data


    def _power_cycle_mimo_device(self):
        """Power Cycle Mimo device"""
        logging.info('Plan to power cycle Mimo')
        try:
            power_cycle_usb_util.power_cycle_usb_vidpid(self._host, self._board,
                 MIMO_VID, MIMO_PID)
        except KeyError:
           raise error.TestFail('Counld\'t find target device: '
                                'vid:pid {}:{}'.format(MIMO_VID, MIMO_PID))


    def _run_power_cycle_mimo_test(self):
        """Power Cycle Mimo device for multiple times"""
        self._power_cycle_mimo_device()
        logging.info('Powercycle done for Mimo %s:%s', MIMO_VID, MIMO_PID)
        time.sleep(LONG_TIMEOUT)
        self._kernel_usb_sanity_test()


    def _check_peripherals(self):
        """
        Check CfM has camera, speaker and Mimo connected.
        @returns list of peripherals found.
        """
        speakers = get_usb_devices._get_speakers(self.usb_data)
        peripherals = []
        for speaker, count in speakers.iteritems():
            logging.info('Detect Audio device %s (%d)',
                         speaker, count)
            if count:
                peripherals.append(speaker)

        cameras = get_usb_devices._get_cameras(self.usb_data)
        for camera, count in cameras.iteritems():
            logging.info('Detect Video device %s (%d)',
                         camera, count)
            if count:
                peripherals.append(camera)

        displays = get_usb_devices._get_display_mimo(self.usb_data)
        mimo_display_count = 0
        for display, count in displays.iteritems():
            logging.info('Detect Mimo displaylink device %s (%d)',
                         display, count)
            if count:
                peripherals.append(display)
                mimo_display_count += 1

        if mimo_display_count != 1:
          raise error.TestFail('Each Set of CfM should have exactly one type'
                               ' of Mimo Display connected. Found %d' % (
                                 mimo_display_count))

        controllers = get_usb_devices._get_controller_mimo(self.usb_data)
        controller_count = 0
        for controller, count in controllers.iteritems():
            logging.info('Detect Mimo controller device %s (%d)',
                         controller, count)
            if count:
                peripherals.append(controller)
                controller_count += 1
        if controller_count != 1:
          raise error.TestFail('Each Set of CfM should have exactly one type'
                               ' of Mimo Controller connected. Found %d' % (
                                   controller_count))
        return peripherals


    def _kernel_usb_sanity_test(self):
        """
        Check connected camera, speaker and Mimo have expected usb interfaces.
        """
        self.usb_data = self._cmd_usb_devices()
        for _key in self.usb_device_list:
            logging.info('Looking for vid:pid (%s)', _key)
            get_usb_devices._verify_usb_device_ok(self.usb_data, _key)


    def _run_reboot_test(self):
        """Reboot testing for Mimo."""

        boot_id = self._host.get_boot_id()
        self._host.reboot()
        self._host.wait_for_restart(old_boot_id=boot_id)
        self.cfm_facade.restart_chrome_for_cfm()
        time.sleep(SHORT_TIMEOUT)
        if self._is_meeting:
            self.cfm_facade.wait_for_meetings_telemetry_commands()
        else:
            self.cfm_facade.wait_for_hangouts_telemetry_commands()
        self.usb_data = self._cmd_usb_devices()
        self._kernel_usb_sanity_test()


    def _run_hangout_test(self) :
        """
        Start a hangout session and end the session after random time.

        @raises error.TestFail if any of the checks fail.
        """
        logging.info('Joining meeting...')
        if self._is_meeting:
            self.cfm_facade.start_meeting_session()
        else:
            self.cfm_facade.start_new_hangout_session('mimo-sanity-test')
        time.sleep(random.randrange(SHORT_TIMEOUT, LONG_TIMEOUT))

        # Verify USB data in-call.
        self.usb_data = self._cmd_usb_devices()
        self._kernel_usb_sanity_test()

        if self._is_meeting:
            self.cfm_facade.end_meeting_session()
        else:
            self.cfm_facade.end_hangout_session()
        logging.info('Session has ended.')

        # Verify USB after leaving the call.
        self.usb_data = self._cmd_usb_devices()
        self._kernel_usb_sanity_test()
        time.sleep(SHORT_TIMEOUT)


    def run_once(self, repetitions, is_meeting):
        """
        Runs the test.

        @param repetitions: amount of reboot cycles to perform.
        """
        # Remove 'board:' prefix.
        self._board = self._host.get_board().split(':')[1]
        self._is_meeting = is_meeting

        self.usb_data = self._cmd_usb_devices()
        if not self.usb_data:
            raise error.TestFail('No usb devices found on DUT.')
        else:
            self.usb_device_list = self._check_peripherals()
            self._kernel_usb_sanity_test()

        if self._is_meeting:
            self.cfm_facade.wait_for_meetings_telemetry_commands()
        else:
            self.cfm_facade.wait_for_hangouts_telemetry_commands()

        for i in xrange(1, repetitions + 1):
            logging.info('Running test cycle %d/%d', i, repetitions)
            self._run_reboot_test()
            self._run_hangout_test()
            self._run_power_cycle_mimo_test()
