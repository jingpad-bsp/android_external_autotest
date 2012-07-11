# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, tempfile

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, httpd
from autotest_lib.client.cros.audio import audio_helper

# Names of mixer controls.
_CONTROL_MASTER = "'Master Playback Volume'"
_CONTROL_HEADPHONE = "'Headphone Playback Volume'"
_CONTROL_SPEAKER = "'Speaker Playback Volume'"
_CONTROL_MIC_BOOST = "'Mic Boost Volume'"
_CONTROL_MIC_CAPTURE = "'Mic Capture Volume'"
_CONTROL_CAPTURE = "'Capture Volume'"
_CONTROL_PCM = "'PCM Playback Volume'"
_CONTROL_DIGITAL = "'Digital Capture Volume'"
_CONTROL_CAPTURE_SWITCH = "'Capture Switch'"

# Default test configuration.
_DEFAULT_CARD = '0'
_DEFAULT_MIXER_SETTINGS = [{'name': _CONTROL_MASTER, 'value': "100%"},
                           {'name': _CONTROL_HEADPHONE, 'value': "100%"},
                           {'name': _CONTROL_SPEAKER, 'value': "0%"},
                           {'name': _CONTROL_MIC_BOOST, 'value': "50%"},
                           {'name': _CONTROL_MIC_CAPTURE, 'value': "50%"},
                           {'name': _CONTROL_PCM, 'value': "100%"},
                           {'name': _CONTROL_DIGITAL, 'value': "100%"},
                           {'name': _CONTROL_CAPTURE, 'value': "100%"},
                           {'name': _CONTROL_CAPTURE_SWITCH, 'value': "on"}]

_DEFAULT_NUM_CHANNELS = 2
_DEFAULT_RECORD_DURATION = 10
# Minimum RMS value to consider a "pass".
_DEFAULT_SOX_RMS_THRESHOLD = 0.20
_DEFAULT_VOLUME_LEVEL = 100
_DEFAULT_CAPTURE_GAIN = 2500

# Media formats to test.
_MEDIA_FORMATS = ['BBB.mp3', 'BBB.mp4', 'BBB_mulaw.wav', 'BBB.ogv', 'BBB.webm']


class desktopui_MediaAudioFeedback(cros_ui_test.UITest):
    version = 1

    def initialize(self,
                   card=_DEFAULT_CARD,
                   mixer_settings=_DEFAULT_MIXER_SETTINGS,
                   num_channels=_DEFAULT_NUM_CHANNELS,
                   record_duration=_DEFAULT_RECORD_DURATION,
                   sox_min_rms=_DEFAULT_SOX_RMS_THRESHOLD,
                   volume_level=_DEFAULT_VOLUME_LEVEL,
                   capture_gain=_DEFAULT_CAPTURE_GAIN):
        """Setup the deps for the test.

        Args:
            card: The index of the sound card to use.
            mixer_settings: Alsa control settings to apply to the mixer before
                starting the test.
            num_channels: The number of channels on the device to test.
            record_duration: How long of a sample to record.
            sox_min_rms: The minimum RMS value to consider a pass.
            volume_level: The level to set the volume to
            capture_gain: what to set the capture gain to (in dB * 100, 2500 =
                25 dB)

        Raises:
            error.TestError if the deps can't be run.
        """
        self._card = card
        self._mixer_settings = mixer_settings
        self._sox_min_rms = sox_min_rms
        self._volume_level = volume_level
        self._capture_gain = capture_gain

        self._ah = audio_helper.AudioHelper(self,
                record_duration=record_duration,
                num_channels=num_channels)
        self._ah.setup_deps(['sox'])

        super(desktopui_MediaAudioFeedback, self).initialize()
        # _test_url must end with '/'.
        self._test_url = 'http://localhost:8000/'
        self._testServer = httpd.HTTPListener(8000, docroot=self.bindir)
        self._testServer.run()

    def run_once(self):
        self._ah.set_volume_levels(self._volume_level, self._capture_gain)
        # Record a sample of "silence" to use as a noise profile.
        with tempfile.NamedTemporaryFile(mode='w+t') as noise_file:
            logging.info('Noise file: %s' % noise_file.name)
            self._ah.record_sample(noise_file.name)
            # Test each media file for all channels.
            for media_file in _MEDIA_FORMATS:
                self._ah.loopback_test_channels(noise_file,
                        lambda channel: self.play_media(media_file),
                        lambda output: self.check_recorded(output, media_file))

    def play_media(self, media_file):
        """Plays a media file in Chromium.

        Args:
            media_file: Media file to test.
        """
        logging.info('Playing back now media file %s.' % media_file)
        self.pyauto.NavigateToURL(self._test_url + media_file)

    def check_recorded(self, sox_output, media_file):
        """Checks if the calculated RMS value is expected.

        Args:
            sox_output: The output from sox stat command.
            media_file: Media file name in case we are testing a media file.

        Raises:
            error.TestFail if the RMS amplitude of the recording isn't above
                the threshold.
        """
        rms_val = self._ah.get_audio_rms(sox_output)

        # In case we don't get a valid RMS value.
        if rms_val is None:
            raise error.TestError(
                'Failed to generate an audio RMS value from playback.')

        logging.info('%s : Got audio RMS value of %f. Minimum pass is %f.' %
                     (media_file, rms_val, self._sox_min_rms))
        if rms_val < self._sox_min_rms:
            raise error.TestError(
                'Audio RMS value %f too low for %s. Minimum pass is %f.' %
                (rms_val, media_file, self._sox_min_rms))
