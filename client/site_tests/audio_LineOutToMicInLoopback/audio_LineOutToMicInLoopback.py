# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.audio import audio_helper
from autotest_lib.client.cros.audio import alsa_utils
from autotest_lib.client.cros.audio import cmd_utils
from autotest_lib.client.cros.audio import cras_utils
from autotest_lib.client.cros.audio import sox_utils


TEST_DURATION = 1

class audio_LineOutToMicInLoopback(test.test):
    """Verifies audio playback and capture function."""
    version = 1
    preserve_srcdir = True

    @staticmethod
    def wait_for_active_stream_count(expected_count):
        utils.poll_for_condition(
            lambda: cras_utils.get_active_stream_count() == expected_count,
            exception=error.TestError(
                'Timeout waiting active stream count to become %d' %
                 expected_count))


    # TODO(owenlin): split this test into two tests for ALSA and CRAS.
    @audio_helper.alsa_rms_test
    def run_once(self):
        """Entry point of this test."""

        # Multitone wav file lasts 10 seconds
        self._wav_path = os.path.join(self.srcdir, '10SEC.wav')

        self.loopback_test_hw()
        self.loopback_test_cras()


    def loopback_test_hw(self):
        logging.info('loopback_test_hw')
        noise_file = os.path.join(self.resultsdir, 'hw_noise.wav')
        recorded_file = os.path.join(self.resultsdir, 'hw_recorded.wav')

        # Record a sample of "silence" to use as a noise profile.
        alsa_utils.record(noise_file, duration=1)

        try:
            p = cmd_utils.popen(alsa_utils.playback_cmd(self._wav_path))

            # Wait one second to make sure the playback has been started.
            time.sleep(1)
            alsa_utils.record(recorded_file, duration=TEST_DURATION)

            # Make sure the audio is still playing.
            if p.poll() != None:
                raise error.TestError('playback stopped')
        finally:
            cmd_utils.kill_or_log_returncode(p)

        audio_helper.reduce_noise_and_check_rms(recorded_file, noise_file)

        # Keep the file if the above check fails
        os.unlink(noise_file)
        os.unlink(recorded_file)


    def loopback_test_cras(self):
        """Uses cras_test_client to test audio on CRAS."""
        logging.info('loopback_test_cras')

        noise_file = os.path.join(self.resultsdir, 'cras_noise.wav')
        recorded_file = os.path.join(self.resultsdir, 'cras_recorded.wav')

        # Record a sample of "silence" to use as a noise profile.
        cras_utils.capture(noise_file, duration=1)

        self.wait_for_active_stream_count(0)
        try:
            p = cmd_utils.popen(cras_utils.playback_cmd(self._wav_path))
            self.wait_for_active_stream_count(1)
            cras_utils.capture(recorded_file, duration=TEST_DURATION)

            # Make sure the audio is still playing.
            if p.poll() != None:
                raise error.TestError('playback stopped')
        finally:
            cmd_utils.kill_or_log_returncode(p)

        audio_helper.reduce_noise_and_check_rms(recorded_file, noise_file)

        # Keep these files if the above check failed
        os.unlink(noise_file)
        os.unlink(recorded_file)
