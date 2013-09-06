# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, tempfile

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

_DEFAULT_NUM_CHANNELS = 2
_DEFAULT_RECORD_DURATION = 10
_DEFAULT_VOLUME_LEVEL = 100
_DEFAULT_CAPTURE_GAIN = 2500

# Media formats to test.
_MEDIA_FORMATS = ['sine440.mp3',
                  'sine440.mp4',
                  'sine440.wav',
                  'sine440.ogv',
                  'sine440.webm']


class desktopui_MediaAudioFeedback(cros_ui_test.UITest):
    """Verifies if media playback can be captured."""
    version = 1

    def initialize(self,
                   num_channels=_DEFAULT_NUM_CHANNELS,
                   record_duration=_DEFAULT_RECORD_DURATION,
                   volume_level=_DEFAULT_VOLUME_LEVEL,
                   capture_gain=_DEFAULT_CAPTURE_GAIN):
        """Setup the deps for the test.

        Args:
            num_channels: The number of channels on the device to test.
            record_duration: How long of a sample to record.
            volume_level: The level to set the volume to
            capture_gain: what to set the capture gain to (in dB * 100, 2500 =
                25 dB)

        Raises:
            error.TestError if the deps can't be run.
        """
        self._volume_level = volume_level
        self._capture_gain = capture_gain
        self._rec_cmd = 'arecord -d %f -f dat' % record_duration
        self._mix_cmd = '/usr/bin/cras_test_client --show_total_rms ' \
                        '--duration_seconds %f --num_channels 2 ' \
                        '--rate 48000 --loopback_file' % record_duration
        self._num_channels = num_channels

        super(desktopui_MediaAudioFeedback, self).initialize()
        self._test_url = 'http://localhost:8000/play.html'
        self._testServer = httpd.HTTPListener(8000, docroot=self.bindir)
        self._testServer.run()

    def run_once(self):
        audio_helper.set_volume_levels(self._volume_level, self._capture_gain)
        if not audio_helper.check_loopback_dongle():
            raise error.TestError('Audio loopback dongle is in bad state.')

        # Record a sample of "silence" to use as a noise profile.
        with tempfile.NamedTemporaryFile(mode='w+t') as noise_file:
            logging.info('Noise file: %s', noise_file.name)
            audio_helper.record_sample(noise_file.name, self._rec_cmd)
            # Test each media file for all channels.
            for media_file in _MEDIA_FORMATS:
                audio_helper.loopback_test_channels(noise_file.name,
                        self.resultsdir,
                        lambda channel: self.play_media(media_file),
                        self.wait_player_end_then_check_recorded,
                        num_channels=self._num_channels,
                        record_command=self._rec_cmd,
                        mix_command=self._mix_cmd)

    def wait_player_end_then_check_recorded(self, sox_output):
        """Wait for player ends playing and then check for recorded result.

        @param sox_output: sox statistics output of recorded wav file.
        """
        if not self.pyauto.WaitUntil(lambda: self.pyauto.ExecuteJavascript("""
                    player_status = document.getElementById('status');
                    window.domAutomationController.send(player_status.innerHTML);
                """), expect_retval='Ended'):
            raise error.TestError('Player never end until timeout.');
        audio_helper.check_audio_rms(sox_output)

    def play_media(self, media_file):
        """Plays a media file in Chromium.

        @param media_file: Media file to test.
        """
        logging.info('Playing back now media file %s.', media_file)

        # Navigate to play.html?<file-name>, javascript test will parse
        # the media file name and play it.
        self.pyauto.NavigateToURL("%s?%s" % (self._test_url, media_file))
