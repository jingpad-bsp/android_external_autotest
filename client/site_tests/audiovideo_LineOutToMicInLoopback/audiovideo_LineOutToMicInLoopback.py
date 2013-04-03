# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, tempfile

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.audio import audio_helper


_DEFAULT_NUM_CHANNELS = 2
_DEFAULT_RECORD_DURATION = 1
_DEFAULT_VOLUME_LEVEL = 100
_DEFAULT_CAPTURE_GAIN = 2500

# Minimum RMS value to consider a "pass".
_DEFAULT_SOX_RMS_THRESHOLD = 0.25


class audiovideo_LineOutToMicInLoopback(test.test):
    """Verifies audio playback and capture function."""
    version = 1
    preserve_srcdir = True

    def initialize(self,
                   num_channels=_DEFAULT_NUM_CHANNELS,
                   record_duration=_DEFAULT_RECORD_DURATION,
                   sox_min_rms=_DEFAULT_SOX_RMS_THRESHOLD,
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

        self._ah = audio_helper.AudioHelper(self,
                sox_threshold=sox_min_rms,
                num_channels=self._num_channels)
        self._ah.setup_deps(['sox', 'audioloop'])

        super(audiovideo_LineOutToMicInLoopback, self).initialize()

    def run_once(self):
        """Entry point of this test."""
        self._ah.set_volume_levels(self._volume_level, self._capture_gain)
        if not self._ah.check_loopback_dongle():
            raise error.TestError('Audio loopback dongle is in bad state.')

        self.loopback_test_hw()
        self.loopback_test_cras()

    def loopback_test_hw(self):
        """Uses aplay and arecord to test audio on internal card"""
        # TODO(hychao): update device parameter for internal card
        self._ah._rec_cmd = ('arecord -f dat -d %d -D plughw' %
                             self._record_duration)

        # Record a sample of "silence" to use as a noise profile.
        with tempfile.NamedTemporaryFile(mode='w+t') as noise_file:
            logging.info('Noise file: %s', noise_file.name)
            self._ah.record_sample(noise_file.name)

            def play_wav(channel):
                """Plays multitone wav using aplay

                   @param channel: Unsed variable
                """
                cmd = ('aplay -D plughw -d %d %s' %
                       (self._record_duration, self._wav_path))
                utils.system(cmd)

            self._ah.loopback_test_channels(noise_file, play_wav)

    def loopback_test_cras(self):
        """Uses cras_test_client to test audio on CRAS."""
        self._ah._rec_cmd = ('cras_test_client --duration_seconds %d '
                             '--capture_file' % self._record_duration)

        # Record a sample of "silence" to use as a noise profile.
        with tempfile.NamedTemporaryFile(mode='w+t') as noise_file:
            logging.info('Noise file: %s', noise_file.name)
            self._ah.record_sample(noise_file.name)

            def play_wav(channel):
                """Plays multitone wav using cras_test_client

                   @param channel: Unsed variable
                """
                cmd = ('cras_test_client --duration_seconds %d '
                       '--num_channels 1 --playback_file %s' %
                       (self._record_duration, self._wav_path))
                utils.system(cmd)

            self._ah.loopback_test_channels(noise_file, play_wav)
