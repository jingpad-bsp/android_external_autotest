# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime, logging, time, random
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib.cros import tpm_utils
from autotest_lib.server import test
from autotest_lib.server.cros.multimedia import remote_facade_factory
from autotest_lib.client.common_lib.cros import get_usb_devices
from autotest_lib.client.common_lib.cros import power_cycle_usb_util


DUT_BOARD = 'guado'
LONG_TIMEOUT = 30
SHORT_TIMEOUT = 5
MIMO_VID = '17e9'
MIMO_PID = '016b'


class enterprise_CFM_MimoSanity(test.test):
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
        usb_devices = (self.client.run('usb-devices', ignore_status=True).
                                         stdout.strip().split('\n\n'))
        usb_data = get_usb_devices._extract_usb_data(
                   '\nUSB-Device\n'+'\nUSB-Device\n'.join(usb_devices))
        return usb_data


    def _power_cycle_mimo_device(self):
        """Power Cycle Mimo device"""
        logging.info('Plan to power cycle Mimo')
        try:
            power_cycle_usb_util.power_cycle_usb_vidpid(self.client, self.board,
                 MIMO_VID, MIMO_PID)
        except KeyError:
           raise error.TestFail('Counld\'t find target device: '
                                'vid:pid {}:{}'.format(MIMO_VID, MIMO_PID))


    def _run_power_cycle_mimo_test(self):
        """Power Cycle Mimo device for multiple times"""
        repeat = self.repeat
        while repeat:
            self._power_cycle_mimo_device()
            logging.info('Powercycle done for Mimo %s:%s', MIMO_VID, MIMO_PID)
            time.sleep(LONG_TIMEOUT)
            self.usb_data = self._cmd_usb_devices()
            self._kernel_usb_sanity_test()
            repeat -= 1


    def _check_peripherals(self):
        """Check CfM has camera, speaker and Mimo connected."""
        speaker_list = get_usb_devices._get_speakers(self.usb_data)
        peripheral_list = []
        not_found = True
        for _key in speaker_list.keys():
            logging.info('Detect Audio device %s = %s',
                         _key, speaker_list[_key])
            if speaker_list[_key] != 0 and not_found:
                not_found = False
                peripheral_list.append(_key)
                continue

        camera_list = get_usb_devices._get_cameras(self.usb_data)
        not_found = True
        for _key in camera_list.keys():
            logging.info('Detect Video device %s = %s',
                         _key, camera_list[_key])
            if camera_list[_key] != 0 and not_found:
                not_found = False
                peripheral_list.append(_key)
                continue

        display_list = get_usb_devices._get_display_mimo(self.usb_data)
        not_found = True
        for _key in display_list.keys():
            logging.info('Detect Mimo displaylink device %s = %s',
                         _key, display_list[_key])
            if display_list[_key] != 0 and not_found:
                not_found = False
                peripheral_list.append(_key)
                continue
            if display_list[_key] != 0 and not not_found:
                raise error.TestFail('Each Set of CfM should have only one type'
                                     ' of Mimo Display connected')
        if not_found:
            raise error.TestFail('Each set of CfM should have at least one'
                                 ' Mimo: Displaylink.')

        controller_list = get_usb_devices._get_controller_mimo(self.usb_data)
        not_found = True
        for _key in controller_list.keys():
            logging.info('Detect Mimo controller device %s = %s',
                         _key, controller_list[_key])

            if controller_list[_key] != 0 and not_found:
                not_found = False
                peripheral_list.append(_key)
                continue
            if controller_list[_key] != 0 and not not_found:
                raise error.TestFail('Each Set of CfM should have only one type'
                                     ' of Mimo Controller connected')
        if not_found:
            raise error.TestFail('Each set of CfM should have at least one'
                                 ' Mimo: SiS Controller.')

        return peripheral_list


    def _kernel_usb_sanity_test(self):
        """Check connected camera, speaker and Mimo have
        expected usb interfaces."""
        for _key in self.usb_device_list:
            state = []
            number, state =  get_usb_devices._is_usb_device_ok(
                               self.usb_data, _key)
            if number < 1:
                raise error.TestFail(
                      'Expect at least one device %s connected,'
                      'actual number of device = %d'
                      % (_key, number))
            if '0' in state:
                raise error.TestFail(
                    'Device %s have unexpected interfaces.' %(_key))


    def _run_reboot_test(self):
        """Reboot testing for Mimo."""
        repeat = self.repeat
        while repeat:
           logging.info('Reboot CfM #: %d',self.rebootno)
           self.rebootno += 1
           self.client.reboot()
           time.sleep(LONG_TIMEOUT)
           self.cfm_facade.restart_chrome_for_cfm()
           time.sleep(SHORT_TIMEOUT)
           if is_meeting:
               self.cfm_facade.wait_for_meetings_landing_page()
           else:
               self.cfm_facade.wait_for_hangouts_telemetry_commands()
           self.usb_data = self._cmd_usb_devices()
           self._kernel_usb_sanity_test()
           self._run_hangout_test(True, 1)
           repeat -= 1


    def _run_hangout_test(self, checkusb, repeat) :
        """Start a hangout session and end the session after random time.
        @raises error.TestFail if any of the checks fail.
        """
        repeat = int(repeat)
        while repeat:
            logging.info('Session name: %s, # %d meet',
                         self.hangout, self.meetno)
            self.meetno += 1
            logging.info('Now joining meeting.........')
            self.cfm_facade.start_new_hangout_session(self.hangout)
            time.sleep(random.randrange(SHORT_TIMEOUT, LONG_TIMEOUT))
            if checkusb:
                self.usb_data = self._cmd_usb_devices()
                self._kernel_usb_sanity_test()
            self.cfm_facade.end_hangout_session()
            repeat -= 1
            logging.info('Meeting is ended................')


    def run_once(self, host, hangout, repeat):
        """Runs the test."""
        self.client = host
        self.board = DUT_BOARD
        self.repeat = repeat
        self.hangout = hangout
        self.meetno = 0
        self.rebootno = 0

        self.usb_data = self._cmd_usb_devices()
        if not self.usb_data:
            raise error.TestFail('No usb devices found on DUT.')
        else:
            self.usb_device_list = self._check_peripherals()
            self._kernel_usb_sanity_test()

        factory = remote_facade_factory.RemoteFacadeFactory(
                  host, no_chrome=True)
        self.cfm_facade = factory.create_cfm_facade()

        tpm_utils.ClearTPMOwnerRequest(self.client)

        if self.client.servo:
            self.client.servo.switch_usbkey('dut')
            self.client.servo.set('usb_mux_sel3', 'dut_sees_usbkey')
            time.sleep(SHORT_TIMEOUT)
            self._set_hub_power(True)

        try:
            self.cfm_facade.enroll_device()
            self.cfm_facade.skip_oobe_after_enrollment()
            if is_meeting:
                self.cfm_facade.wait_for_meetings_landing_page()
            else:
                self.cfm_facade.wait_for_hangouts_telemetry_commands()
            raise error.TestFail(str(e))

        self.cfm_facade.set_preferred_camera(
              get_usb_devices._get_preferred_camera(self.usb_device_list))
        logging.info('PEFERRED camera is set to %s',
                     self.cfm_facade.get_preferred_camera())
        self.cfm_facade.set_preferred_speaker(
            get_usb_devices._get_preferred_speaker(self.usb_device_list))
        logging.info('PEFERRED speaker is set to %s',
                     self.cfm_facade.get_preferred_speaker())

        self._run_reboot_test()
        self._run_power_cycle_mimo_test()
