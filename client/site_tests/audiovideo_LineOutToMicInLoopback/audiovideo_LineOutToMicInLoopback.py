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


_DEFAULT_NUM_CHANNELS = 2
_DEFAULT_RECORD_DURATION = 1
_DEFAULT_VOLUME_LEVEL = 100
_DEFAULT_CAPTURE_GAIN = 2500
_DEFAULT_RMS_THRESHOLD = 0.05


class audiovideo_LineOutToMicInLoopback(test.test):
    """Verifies audio playback and capture function."""
    version = 1
    preserve_srcdir = True

    def initialize(self,
                   num_channels=_DEFAULT_NUM_CHANNELS,
                   record_duration=_DEFAULT_RECORD_DURATION,
                   volume_level=_DEFAULT_VOLUME_LEVEL,
                   capture_gain=_DEFAULT_CAPTURE_GAIN):
        """ Setup the deps for the test.

            @param num_channels: The number of channels on the device to test.
            @param record_duration: How long of a sample to record.
            @param volume_level: The playback volume to set.
            @param capture_gain: The capture gain to set.
        """
        self._num_channels = num_channels
        self._record_duration = record_duration
        self._volume_level = volume_level
        self._capture_gain = capture_gain

        # Multitone wav file lasts 10 seconds
        self._wav_path = os.path.join(self.srcdir, '10SEC.wav')

        super(audiovideo_LineOutToMicInLoopback, self).initialize()

    def run_once(self):
        """Entry point of this test."""

        # Config the playback volume and recording gain.
        cras_utils.set_system_volume(self._volume_level)
        output_node, _ = cras_utils.get_selected_nodes()
        cras_utils.set_node_volume(output_node, self._volume_level)
        cras_utils.set_capture_gain(self._capture_gain)

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
            sox_utils.noise_profile(noise_file, noise_profile.name, channels=1)
            sox_utils.noise_reduce(
                    recorded_file, reduced_file.name, noise_profile.name,
                    channels=1)
            stat = sox_utils.get_stat(reduced_file.name, channels=1)
            logging.info('stat: %s', str(stat))
            if stat.rms < _DEFAULT_RMS_THRESHOLD:
                raise error.TestFail('RMS: %s' % stat.rms)


    def loopback_test_hw(self):
        logging.info('loopback_test_hw')
        noise_file = os.path.join(self.resultsdir, 'hw_noise.wav')
        recorded_file = os.path.join(self.resultsdir, 'hw_recorded.wav')

        # Record a sample of "silence" to use as a noise profile.
        alsa_utils.record(
                noise_file, duration=self._record_duration, channels=1)

        p1 = cmd_utils.popen(alsa_utils.playback_cmd(
                self._wav_path, duration=self._record_duration))
        p2 = cmd_utils.popen(alsa_utils.record_cmd(
                recorded_file, duration=self._record_duration))

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
        cras_utils.capture(
                noise_file, duration=self._record_duration, channels=1)

        p1 = cmd_utils.popen(cras_utils.playback_cmd(
                self._wav_path, duration=self._record_duration))
        p2 = cmd_utils.popen(cras_utils.capture_cmd(
                recorded_file, duration=self._record_duration, channels=1))

        cmd_utils.wait_and_check_returncode(p1, p2)
        self._check_rms(noise_file, recorded_file)

        # Keep the file if the above check fails
        os.unlink(noise_file)
        os.unlink(recorded_file)
