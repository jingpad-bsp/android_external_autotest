# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.audio import audio_helper

_DEFAULT_NUM_CHANNELS = 2
_DEFAULT_RECORD_DURATION = 15
_DEFAULT_VOLUME_LEVEL = 100
_DEFAULT_CAPTURE_GAIN = 2500

_PLAYER_READY_TIMEOUT = 45


class desktopui_AudioFeedback(test.test):
    """Verifies if youtube playback can be captured."""
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

        super(desktopui_AudioFeedback, self).initialize()

    def play_video(self, player_ready_callback, tab):
        """Plays a Youtube video to record audio samples.

           Skipping initial 60 seconds so we can ignore initial silence
           in the video.

           @param player_ready_callback: callback when yt player is ready.
           @param tab: the tab to load page for testing.
        """
        tab.Navigate(self._test_url)
        tab.WaitForDocumentReadyStateToBeComplete()

        utils.poll_for_condition(
            condition=lambda: tab.EvaluateJavaScript('getPlayerStatus()') ==
                    'player ready',
            exception=error.TestError('Failed to load the Youtube player'),
            sleep_interval=1,
            timeout=_PLAYER_READY_TIMEOUT)

        tab.ExecuteJavaScript('seekAndPlay()')
        if player_ready_callback:
            player_ready_callback()

    def run_once(self):
        """Entry point of this test."""
        if not audio_helper.check_loopback_dongle():
            raise error.TestError('Audio loopback dongle is in bad state.')

        # Record a sample of "silence" to use as a noise profile.
        noise_file_name = audio_helper.create_wav_file(self.resultsdir, "noise")
        audio_helper.record_sample(noise_file_name, self._rec_cmd)

        with chrome.Chrome() as cr:
            cr.browser.SetHTTPServerDirectories(self.bindir)
            self._test_url = cr.browser.http_server.UrlOf('youtube.html')
            logging.info('Playing back youtube media file %s.', self._test_url)

            # Set volume and capture gain after Chrome is up, or those value
            # will be overriden by Chrome.
            audio_helper.set_volume_levels(self._volume_level, self._capture_gain)

            # Play the same video to test all channels.
            self.play_video(lambda: audio_helper.loopback_test_channels(
                                            noise_file_name,
                                            self.resultsdir,
                                            num_channels=self._num_channels,
                                            record_command=self._rec_cmd,
                                            mix_command=self._mix_cmd),
                            cr.browser.tabs[0])
