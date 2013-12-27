# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import tempfile
import time

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.audio import audio_helper
from autotest_lib.client.cros.audio import cmd_utils
from autotest_lib.client.cros.audio import cras_utils
from autotest_lib.client.cros.audio import sox_utils

_TEST_SAMPLE_RATES = [ 8000,
                       16000,
                       22050,
                       32000,
                       44100,
                       48000,
                       88200,
                       96000,
                       192000 ]
# Minimum RMS value to consider a "pass".  Can't be too high because we don't
# know how much or our recording will be silence waiting for the tone to start.
_MIN_SOX_RMS_VALUE = 0.05

_TEST_TONE_ONE = 440
_TEST_TONE_TWO = 523

class audio_CRASFormatConversion(test.test):
    version = 1

    def play_sine_tone(self, frequence, rate):
        """Plays a sine tone by cras and returns the processes.
        Args:
            frequence: the frequence of the sine wave.
            rate: the sampling rate.
        """
        p1 = cmd_utils.popen(
            sox_utils.generate_sine_tone_cmd(
                    filename='-', rate=rate, frequence=frequence, gain=-6),
            stdout=cmd_utils.PIPE)
        p2 = cmd_utils.popen(
            cras_utils.playback_cmd(
                    playback_file='-', buffer_frames=512, rate=rate),
            stdin=p1.stdout)
        return [p1, p2]


    def wait_for_active_stream_count(self, expected_count):
        utils.poll_for_condition(
                lambda: cras_utils.get_active_stream_count() == expected_count,
                exception=error.TestError(
                        'Timeout waiting active stream count to become %d' %
                        expected_count),
                timeout=1, sleep_interval=0.05)

    def loopback(self, noise_profile, primary, secondary):
        """ Plays two different tones (the 440 and 523 Hz sine wave) at the
            specified sampling rate and make sure the sounds is recorded
        Args:
            noise_profile: The noise profile which is used to reduce the
                           noise of the recored audio.
            primary: The sample rate to play first, HW will be set to this.
            secondary: The second sample rate, will be SRC'd to the first.
        """
        popens = []

        record_file = os.path.join(self.resultsdir,
                'record-%s-%s.wav' % (primary, secondary))

        # There should be no other active streams.
        self.wait_for_active_stream_count(0)

        # Start with the primary sample rate, then add the secondary.  This
        # causes the secondary to be SRC'd to the primary rate.
        try:
            # Play the first audio stream and make sure it has been played
            popens += self.play_sine_tone(_TEST_TONE_ONE, primary)
            self.wait_for_active_stream_count(1)

            # Play the second audio stream and make sure it has been played
            popens += self.play_sine_tone(_TEST_TONE_TWO, secondary)
            self.wait_for_active_stream_count(2)

            cras_utils.capture(
                    record_file, buffer_frames=441, duration=1, rate=44100)

            # Make sure the playback is still in good shape
            if any(p.poll() is not None for p in popens):
                # We will log more details later in finally.
                raise error.TestFail('process unexpectly stopped')

            reduced_file = tempfile.NamedTemporaryFile()
            sox_utils.noise_reduce(
                    record_file, reduced_file.name, noise_profile, rate=44100)

            sox_stat = sox_utils.get_stat(reduced_file.name, rate=44100)

            logging.info('The sox stat of (%d, %d) is %s',
                         primary, secondary, str(sox_stat))

            if sox_stat.rms < _MIN_SOX_RMS_VALUE:
               raise error.TestFail('RMS: %s' % sox_stat.rms)

            # Remove the file only when we pass the test
            os.unlink(record_file)
        finally:
            cmd_utils.kill_or_log_returncode(*popens)

    @audio_helper.cras_rms_test
    def run_once(self):
        """Runs the format conversion test.
        """

        # Record silence to use as the noise profile.
        noise_file = os.path.join(self.resultsdir, "noise.wav")
        noise_profile = tempfile.NamedTemporaryFile()
        cras_utils.capture(noise_file, buffer_frames=512, duration=1)
        sox_utils.noise_profile(noise_file, noise_profile.name)

        # Try all sample rate pairs.
        for primary in _TEST_SAMPLE_RATES:
            for secondary in _TEST_SAMPLE_RATES:
                self.loopback(noise_profile.name, primary, secondary)

        # Record at all sample rates
        record_file = tempfile.NamedTemporaryFile()
        for rate in _TEST_SAMPLE_RATES:
            cras_utils.capture(
                    record_file.name, buffer_frames=512, duration=1, rate=rate)

        os.unlink(noise_file)
