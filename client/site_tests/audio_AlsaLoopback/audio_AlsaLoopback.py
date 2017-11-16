# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, time

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.audio import audio_helper
from autotest_lib.client.cros.audio import alsa_utils
from autotest_lib.client.cros.audio import cmd_utils
from autotest_lib.client.cros.audio import cras_utils


TEST_DURATION = 1

class audio_AlsaLoopback(audio_helper.alsa_rms_test):
    """Verifies audio playback and capture function."""
    version = 1

    def run_once(self):
        """Entry point of this test."""

        # Multitone wav file lasts 10 seconds
        wav_path = os.path.join(self.bindir, '10SEC.wav')

        noise_file = os.path.join(self.resultsdir, 'hw_noise.wav')
        recorded_file = os.path.join(self.resultsdir, 'hw_recorded.wav')

        # Record a sample of "silence" to use as a noise profile.
        alsa_utils.record(noise_file, duration=1)

        # Get selected input and output devices.
        cras_input = cras_utils.get_selected_input_device_name()
        cras_output = cras_utils.get_selected_output_device_name()
        logging.debug("Selected input=%s, output=%s", cras_input, cras_output)
        if cras_input is None:
            raise error.TestFail("Fail to get selected input device.")
        if cras_output is None:
            raise error.TestFail("Fail to get selected output device.")
        alsa_input = alsa_utils.convert_device_name(cras_input)
        alsa_output = alsa_utils.convert_device_name(cras_output)

        (output_type, input_type) = cras_utils.get_selected_node_types()
        if 'MIC' not in input_type:
            raise error.TestFail("Wrong input type=%s", input_type)
        if 'HEADPHONE' not in output_type:
            raise error.TestFail("Wrong output type=%s", output_type)

        p = cmd_utils.popen(alsa_utils.playback_cmd(wav_path, device=alsa_output))
        try:
            # Wait one second to make sure the playback has been started.
            time.sleep(1)
            alsa_utils.record(recorded_file, duration=TEST_DURATION,
                              device=alsa_input)

            # Make sure the audio is still playing.
            if p.poll() != None:
                raise error.TestError('playback stopped')
        finally:
            cmd_utils.kill_or_log_returncode(p)

        rms_value = audio_helper.reduce_noise_and_get_rms(
            recorded_file, noise_file)[0]

        self.write_perf_keyval({'rms_value': rms_value})

