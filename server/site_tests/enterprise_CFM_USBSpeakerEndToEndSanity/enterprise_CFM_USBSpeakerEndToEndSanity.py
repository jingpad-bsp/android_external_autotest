# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime, time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import tpm_utils
from autotest_lib.client.cros.chameleon import motor_board
from autotest_lib.server import test
from autotest_lib.server.cros.multimedia import remote_facade_factory


_SHORT_TIMEOUT = 2
_LONG_TIMEOUT = 5


class enterprise_CFM_USBSpeakerEndToEndSanity(test.test):
    """Volume changes made in the CFM / hotrod app should be accurately
    reflected in CrOS.
    """
    version = 1


    def start_hangout_session(self):
        """Start a hangout session.

        @param webview_context: Context for hangouts webview.
        @raises error.TestFail if any of the checks fail.
        """
        current_time = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        hangout_name = 'auto-hangout-' + current_time

        self.cfm_facade.start_new_hangout_session(hangout_name)

        if self.cfm_facade.is_ready_to_start_hangout_session():
            raise error.TestFail('Is already in hangout session and should not '
                                 'be able to start another session.')

        time.sleep(_SHORT_TIMEOUT)

        if self.cfm_facade.is_mic_muted():
            self.cfm_facade.unmute_mic()


    def end_hangout_session(self):
        """End hangout session.

        @param webview_context: Context for hangouts window.
        """
        self.cfm_facade.end_hangout_session()

        if self.cfm_facade.is_in_hangout_session():
            raise error.TestFail('CFM should not be in hangout session.')


    def test_increase_volume_button_on_speaker(self, cmd):
        old_cras_volume = [s.strip() for s in
                         self.client.run_output(cmd).splitlines()]

        self.motor.Touch(motor_board.ButtonFunction.VOL_UP)
        self.motor.Release(motor_board.ButtonFunction.VOL_UP)

        new_cras_volume = [s.strip() for s in
                         self.client.run_output(cmd).splitlines()]

        if not new_cras_volume > old_cras_volume:
            raise error.TestFail('Speaker volume increase not reflected in '
                                 'cras volume output. Volume before button '
                                 'press: %s; volume after button press: %s.'
                                 % (old_cras_volume, new_cras_volume))


    def test_decrease_volume_button_on_speaker(self, cmd):
        old_cras_volume = [s.strip() for s in
                         self.client.run_output(cmd).splitlines()]

        self.motor.Touch(motor_board.ButtonFunction.VOL_DOWN)
        self.motor.Release(motor_board.ButtonFunction.VOL_DOWN)

        new_cras_volume = [s.strip() for s in
                         self.client.run_output(cmd).splitlines()]

        if not new_cras_volume < old_cras_volume:
            raise error.TestFail('Speaker volume decrease not reflected in '
                                 'cras volume output. Volume before button '
                                 'press: %s; volume after button press: %s.'
                                 % (old_cras_volume, new_cras_volume))

    def test_call_hangup_button_on_speaker(self):
        self.motor.Touch(motor_board.ButtonFunction.HANG_UP)
        self.motor.Release(motor_board.ButtonFunction.HANG_UP)


    def test_call_button_on_speaker(self):
        self.motor.Touch(motor_board.ButtonFunction.CALL)
        self.motor.Release(motor_board.ButtonFunction.CALL)


    def test_mute_button_on_speaker(self):
        self.motor.Touch(motor_board.ButtonFunction.MUTE)
        self.motor.Release(motor_board.ButtonFunction.MUTE)


    def run_once(self, host, repeat, cmd):
        """Runs the test."""
        self.client = host
        self.chameleon_board = self.client.chameleon

        factory = remote_facade_factory.RemoteFacadeFactory(
                host, no_chrome=True)
        self.cfm_facade = factory.create_cfm_facade()

        self.motor = self.chameleon_board.get_motor_board()

        tpm_utils.ClearTPMOwnerRequest(self.client)

        if self.client.servo:
            self.client.servo.switch_usbkey('dut')
            self.client.servo.set('usb_mux_sel3', 'dut_sees_usbkey')
            time.sleep(_LONG_TIMEOUT)
            self.client.servo.set('dut_hub1_rst1', 'off')
            time.sleep(_LONG_TIMEOUT)

        try:
            self.cfm_facade.enroll_device()
            self.cfm_facade.skip_oobe_after_enrollment()
            self.test_increase_volume_button_on_speaker(cmd)
            self.test_decrease_volume_button_on_speaker(cmd)
            self.test_call_hangup_button_on_speaker()
            self.test_call_button_on_speaker()
            self.test_mute_button_on_speaker()
        except Exception as e:
            raise error.TestFail(str(e))
        finally:
            tpm_utils.ClearTPMOwnerRequest(self.client)
