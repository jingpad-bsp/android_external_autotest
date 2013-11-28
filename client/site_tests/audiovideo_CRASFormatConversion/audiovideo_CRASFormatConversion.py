# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import subprocess
import tempfile

from autotest_lib.client.bin import test
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
# Input and output levels.
_TEST_VOLUME_LEVEL = 100
_TEST_CAPTURE_GAIN = 2500

_TEST_TONE_ONE = 440
_TEST_TONE_TWO = 523

class audiovideo_CRASFormatConversion(test.test):
    version = 1

    def play_sine_tone(self, frequence, rate):
        """Plays a sine tone by cras and returns the processes.
        Args:
            frequence: the frequence of the sine wave.
            rate: the sampling rate.
        """
        p1 = cmd_utils.popen(
            sox_utils.generate_sine_tone_cmd(
                    filename='-', duration=2, rate=rate, frequence=frequence,
                    gain=-6),
            stdout=subprocess.PIPE)
        p2 = cmd_utils.popen(
            cras_utils.playback_cmd(
                    playback_file='-', buffer_frames=512, rate=rate),
            stdin=p1.stdout)
        return [p1, p2]

    def play_two_freqs(self, primary, secondary):
        """ Starts a stream at primary sample rate, adds a stream at secondary.
        Args:
            primary: The sample rate to play first, HW will be set to this.
            secondary: The second sample rate, will be SRC'd to the first.
        """
        processes = []

        # Start with the primary sample rate, then add the secondary.  This
        # causes the secondary to be SRC'd to the primary rate.
        processes += self.play_sine_tone(_TEST_TONE_ONE, primary)
        processes += self.play_sine_tone(_TEST_TONE_TWO, secondary)
        cmd_utils.wait_and_check_returncode(*processes)

    def run_once(self):
        """Runs the format conversion test.
        """

        # Config the playback volume and recording gain
        cras_utils.set_system_volume(_TEST_VOLUME_LEVEL)
        output_node, _ = cras_utils.get_selected_nodes()
        cras_utils.set_node_volume(output_node, _TEST_VOLUME_LEVEL)
        cras_utils.set_capture_gain(_TEST_CAPTURE_GAIN)

        # Record silence to use as the noise profile.
        noise_file = tempfile.NamedTemporaryFile(mode='w+t');
        cras_utils.capture(
                noise_file.name, buffer_frames=512, duration=1, rate=48000)

        def record_callback(filename):
            cras_utils.capture(
                    filename, buffer_frames=441, duration=2, rate=44100)

        # Try all sample rate pairs.
        for primary in _TEST_SAMPLE_RATES:
            for secondary in _TEST_SAMPLE_RATES:
                audio_helper.loopback_test_channels(
                        noise_file.name,
                        self.resultsdir,
                        lambda channel: self.play_two_freqs(primary, secondary),
                        lambda out: audio_helper.check_audio_rms(
                                out, sox_threshold=_MIN_SOX_RMS_VALUE),
                        record_callback=record_callback)

        # Record at all sample rates
        record_file = tempfile.NamedTemporaryFile(mode='w+t');
        for rate in _TEST_SAMPLE_RATES:
            cras_utils.capture(
                    record_file.name, buffer_frames=512, duration=1, rate=rate)
