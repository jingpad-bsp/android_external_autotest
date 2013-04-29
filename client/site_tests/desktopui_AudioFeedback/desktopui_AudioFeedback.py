# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, httpd
from autotest_lib.client.cros.audio import audio_helper

_DEFAULT_NUM_CHANNELS = 2
_DEFAULT_RECORD_DURATION = 15
_DEFAULT_VOLUME_LEVEL = 100
_DEFAULT_CAPTURE_GAIN = 2500


class desktopui_AudioFeedback(cros_ui_test.UITest):
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

        cmd_rec = 'arecord -d %f -f dat' % record_duration
        self._ah = audio_helper.AudioHelper(self,
                record_command=cmd_rec,
                num_channels=num_channels)
        self._ah.setup_deps(['audioloop', 'sox'])

        super(desktopui_AudioFeedback, self).initialize()
        self._test_url = 'http://localhost:8000/youtube.html'
        self._testServer = httpd.HTTPListener(8000, docroot=self.bindir)
        self._testServer.run()

    def run_once(self):
        """Entry point of this test."""
        self._ah.set_volume_levels(self._volume_level, self._capture_gain)
        if not self._ah.check_loopback_dongle():
            raise error.TestError('Audio loopback dongle is in bad state.')

        # Record a sample of "silence" to use as a noise profile.
        noise_file_name = self._ah.create_wav_file("noise")
        self._ah.record_sample(noise_file_name)

        # Play the same video to test all channels.
        self.play_video(lambda: self._ah.loopback_test_channels(
                noise_file_name))

    def play_video(self, player_ready_callback):
        """Plays a Youtube video to record audio samples.

           Skipping initial 60 seconds so we can ignore initial silence
           in the video.

           @param player_ready_callback: callback when yt player is ready.
        """
        logging.info('Playing back youtube media file %s.', self._test_url)
        self.pyauto.NavigateToURL(self._test_url)

        # Default automation timeout is 45 seconds.
        if not self.pyauto.WaitUntil(lambda: self.pyauto.ExecuteJavascript("""
                    player_status = document.getElementById('player_status');
                    window.domAutomationController.send(player_status.innerHTML);
               """), expect_retval='player ready'):
            raise error.TestError('Failed to load the Youtube player')
        self.pyauto.ExecuteJavascript("""
            ytplayer.pauseVideo();
            ytplayer.seekTo(60, true);
            ytplayer.playVideo();
            window.domAutomationController.send('');
        """)
        if player_ready_callback:
            player_ready_callback()
