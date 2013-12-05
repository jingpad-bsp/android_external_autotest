# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, tempfile

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.audio import audio_helper
from autotest_lib.client.cros.audio import alsa_utils
from autotest_lib.client.cros.audio import cmd_utils
from autotest_lib.client.cros.audio import cras_utils
from autotest_lib.client.cros.audio import sox_utils


TEST_DURATION = 1
VOLUME_LEVEL = 100
CAPTURE_GAIN = 2500
RMS_THRESHOLD = 0.05

class audiovideo_LineOutToMicInLoopback(test.test):
    """Verifies audio playback and capture function."""
    version = 1
    preserve_srcdir = True


    def run_once(self):
        """Entry point of this test."""

        # Multitone wav file lasts 10 seconds
        self._wav_path = os.path.join(self.srcdir, '10SEC.wav')

        # Config the playback volume and recording gain.
        cras_utils.set_system_volume(VOLUME_LEVEL)
        output_node, _ = cras_utils.get_selected_nodes()
        cras_utils.set_node_volume(output_node, VOLUME_LEVEL)
        cras_utils.set_capture_gain(CAPTURE_GAIN)

        # CRAS does not apply the volume and capture gain to ALSA until
        # streams are added. Do that to ensure the values have been set.
        cras_utils.playback('-')
        cras_utils.capture('/dev/null', duration=0.1)

        if not audio_helper.check_loopback_dongle():
            raise error.TestError('Audio loopback dongle is in bad state.')

        self.loopback_test_hw()
        self.loopback_test_cras()


    def _check_rms(self, noise_file, recorded_file):
        with tempfile.NamedTemporaryFile() as noise_profile,\
             tempfile.NamedTemporaryFile() as reduced_file:
            sox_utils.noise_profile(noise_file, noise_profile.name)
            sox_utils.noise_reduce(
                    recorded_file, reduced_file.name, noise_profile.name)
            stat = sox_utils.get_stat(reduced_file.name)
            logging.info('stat: %s', str(stat))
            if stat.rms < RMS_THRESHOLD:
                raise error.TestFail('RMS: %s' % stat.rms)


    def loopback_test_hw(self):
        logging.info('loopback_test_hw')
        noise_file = os.path.join(self.resultsdir, 'hw_noise.wav')
        recorded_file = os.path.join(self.resultsdir, 'hw_recorded.wav')

        # Record a sample of "silence" to use as a noise profile.
        alsa_utils.record(noise_file, duration=TEST_DURATION)

        p1 = cmd_utils.popen(alsa_utils.playback_cmd(
                self._wav_path, duration=TEST_DURATION))
        p2 = cmd_utils.popen(alsa_utils.record_cmd(
                recorded_file, duration=TEST_DURATION))

        cmd_utils.wait_and_check_returncode(p1, p2)
        self._check_rms(noise_file, recorded_file)

        # Keep the file if the above check fails
        os.unlink(noise_file)
        os.unlink(recorded_file)


    def loopback_test_cras(self):
        """Uses cras_test_client to test audio on CRAS."""
        logging.info('loopback_test_cras')

        noise_file = os.path.join(self.resultsdir, 'cras_noise.wav')
        recorded_file = os.path.join(self.resultsdir, 'cras_recorded.wav')

        # Record a sample of "silence" to use as a noise profile.
        cras_utils.capture(noise_file, duration=TEST_DURATION)

        p1 = cmd_utils.popen(cras_utils.playback_cmd(
                self._wav_path, duration=TEST_DURATION))
        p2 = cmd_utils.popen(cras_utils.capture_cmd(
                recorded_file, duration=TEST_DURATION))

        cmd_utils.wait_and_check_returncode(p1, p2)
        self._check_rms(noise_file, recorded_file)

        # Keep these files if the above check failed
        os.unlink(noise_file)
        os.unlink(recorded_file)
