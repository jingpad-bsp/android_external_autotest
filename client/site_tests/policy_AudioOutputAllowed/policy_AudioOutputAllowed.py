# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import utils

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.audio import audio_helper
from autotest_lib.client.cros.audio import audio_test_data
from autotest_lib.client.cros.audio import cmd_utils
from autotest_lib.client.cros.audio import cras_utils
from autotest_lib.client.cros.enterprise import enterprise_policy_base
from autotest_lib.client.cros.input_playback import input_playback


class policy_AudioOutputAllowed(
        enterprise_policy_base.EnterprisePolicyTest):
    version = 1

    POLICY_NAME = 'AudioOutputAllowed'
    # How long (sec) to capture output for
    SAMPLE_DURATION = 1
    # The acceptable RMS volume threshold when muted
    MUTE_THRESHOLD = 0.05

    TEST_CASES = {
        'NotSet_Allow': None,
        'True_Allow': True,
        'False_Block': False
    }

    def initialize(self, **kwargs):
        """Initialize objects for test."""
        super(policy_AudioOutputAllowed, self).initialize(**kwargs)
        audio_helper.cras_rms_test_setup()


    def cleanup(self):
        super(policy_AudioOutputAllowed, self).cleanup()


    def wait_for_active_stream_count(self, expected_count):
        """
        Waits for there to be the expected number of audio streams.

        @param expected_count: Number of audio streams to wait for.

        @raises error.TestError: if there is a timeout before the there is the
        desired number of audio streams.

        """
        utils.poll_for_condition(
            lambda: cras_utils.get_active_stream_count() == expected_count,
            exception=error.TestError(
                'Timeout waiting active stream count to become %d' %
                 expected_count))


    def is_muted(self):
        """
        Returns mute status of system.

        @returns: True if system muted, False if not.

        """
        MUTE_STATUS = 'Muted'
        CTC_GREP_FOR_MUTED = 'cras_test_client --dump_server_info | grep muted'

        output = utils.system_output(CTC_GREP_FOR_MUTED)
        muted = output.split(':')[-1].strip()
        return muted == MUTE_STATUS


    def _test_audio_disabled(self, policy_value):
        """
        Verify the AudioOutputAllowed policy behaves as expected.

        Generate and play a sample audio file. When enabled, the RMS for
        the loopback audio must be below the MUTE_THRESHOLD, and when disabled,
        the RMS should be above that value.

        @param policy_value: policy value for this case.

        @raises error.TestFail: In the case where the audio behavior
            does not match the policy value.

        """
        audio_allowed = policy_value or policy_value is None

        RAW_FILE = os.path.join(self.enterprise_dir, 'test_audio.raw')
        recorded_file = os.path.join(self.resultsdir, 'cras_recorded.raw')

        # Play the audio file and capture the output
        self.wait_for_active_stream_count(0)
        p = cmd_utils.popen(cras_utils.playback_cmd(RAW_FILE))
        try:
            self.wait_for_active_stream_count(1)
            cras_utils.capture(recorded_file, duration=self.SAMPLE_DURATION)

            if p.poll() is not None:
                raise error.TestError('Audio playback stopped prematurely')
        finally:
            cmd_utils.kill_or_log_returncode(p)

        rms_value = audio_helper.get_rms(recorded_file)[0]

        if audio_allowed and rms_value <= self.MUTE_THRESHOLD:
            raise error.TestFail('RMS (%s) is too low for audio enabled'
                                 % rms_value)
        elif not audio_allowed and rms_value > self.MUTE_THRESHOLD:
            raise error.TestFail('Audio not muted. RMS = %s' % rms_value)


    def _test_unmute_disabled(self, policy_value):
        """
        Verify AudioOutputAllowed does not allow unmuting when disabled.

        Attempt to unmute the system with CRAS and check the system state
        after.

        @param policy_value: policy value for this case.

        @raises error.TestFail: In the case where the audio behavior
            does not match the policy value.

        """
        audio_allowed = policy_value or policy_value is None

        cras_utils.set_system_mute(False)

        if not audio_allowed and not self.is_muted():
            raise error.TestFail('System should be muted, but is not')
        elif audio_allowed and self.is_muted():
            raise error.TestFail('System is muted but should not be')


    def run_once(self, case):
        """
        Setup and run the test configured for the specified test case.

        @param case: Name of the test case to run.

        """
        case_value = self.TEST_CASES[case]
        self.setup_case(user_policies={self.POLICY_NAME: case_value})
        self._test_audio_disabled(case_value)
        self._test_unmute_disabled(case_value)
