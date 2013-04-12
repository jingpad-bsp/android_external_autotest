# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, httpd

WAIT_TIMEOUT_S = 5
PLAYBACK_TEST_TIME_S = 10
PLAYER_PLAYING_STATE = 'Playing'
PLAYER_PAUSE_STATE = 'Paused'
PLAYER_ENDED_STATE = 'Ended'

class video_YouTubeHTML5(cros_ui_test.UITest):
    """This test verify the YouTube HTML5 video.

    - verify the video playback.
    - verify the available video resolutions.
    - verify the player functionalities.
    """
    version = 1

    def initialize(self):
        super(video_YouTubeHTML5, self).initialize()
        self._driver = self.pyauto.NewWebDriver()
        self._video_duration = 0
        self._testServer = httpd.HTTPListener(8000, docroot=self.bindir)
        self._testServer.run()

    def cleanup(self):
        if self._testServer:
            self._testServer.stop()
        super(video_YouTubeHTML5, self).cleanup()

    def video_current_time(self):
        """Returns video's current playback time.

        Returns:
            returns the current playback location in seconds (int).
        """
        return int(self._driver.execute_script(
                   'return player.getCurrentTime()'))

    def get_player_status(self):
        """Returns the player status."""
        js = 'return playerStatus.innerHTML'
        return self._driver.execute_script(js)

    def get_video_duration(self):
        """Returns the video duration."""
        return int(self._driver.execute_script(
                   'return player.getDuration()'))

    def set_playback_quality(self, quality):
        """Set the video quality to the quality passed in the arg."""
        self._driver.execute_script(
            'player.setPlaybackQuality("%s")' % quality)

    def get_playback_quality(self):
        """Returns the playback quality."""
        return self._driver.execute_script(
               'return player.getPlaybackQuality()')

    def wait_for_player_state(self, expected_status):
        """Wait till the player status changes to expected_status.

        If the status doesn't change for long, the test will time out after
        WAIT_TIMEOUT_S and fails.
        """
        wait_time = 0 # seconds
        while self.get_player_status() != expected_status:
            time.sleep(1)
            if wait_time > WAIT_TIMEOUT_S:
                player_status = self.get_player_status()
                raise error.TestError(
                    'Video failed to load. Player expected status: %s'
                    'and current status: %s.'
                    % (expected_status, player_status))
            wait_time += 1

    def verify_video_playback(self):
        """Verify the video playback."""
        logging.info('Verifying the YouTube video playback')
        playback = 0 # seconds
        prev_playback = 0
        while (self.video_current_time() < self._video_duration
               and playback < PLAYBACK_TEST_TIME_S):
            time.sleep(1)
            if self.video_current_time() <= prev_playback:
                player_status = self.get_player_status()
                raise error.TestError(
                    'Video is not playing. Player status: %s.' % player_status)
            prev_playback = self.video_current_time()
            playback = playback + 1

    def verify_video_resolutions(self):
        """Verify available video resolutions like 360p, 480p, 720p and
           1080p.
        """
        logging.info('Verifying the video resolutions.')
        video_qualities = self._driver.execute_script(
                          'return player.getAvailableQualityLevels()')
        if not video_qualities:
            raise error.TestError(
                'Player failed to return available video qualities.')
        for quality in video_qualities:
            logging.info('Playing video in %s quality.' % quality)
            self.set_playback_quality(quality)
            self.wait_for_player_state(PLAYER_PLAYING_STATE)
            current_quality = self.get_playback_quality()
            if quality != current_quality:
                 raise error.TestError(
                     'Expected video quality: %s. Current video quality: %s'
                     % (quality, current_quality))

    def verify_player_states(self):
        """Verify the player states like play, pause, ended and seek."""
        logging.info('Verifying the player states.')
        self._driver.execute_script('player.pauseVideo()')
        self.wait_for_player_state(PLAYER_PAUSE_STATE)
        self._driver.execute_script('player.playVideo()')
        self.wait_for_player_state(PLAYER_PLAYING_STATE)
        # We are seeking the player position to (video length - 2 seconds).
        # Since the player waits for WAIT_TIMEOUT_S for the status change,
        # the video should be ended before we hit the timeout.
        video_end_test_duration = (self._video_duration -
                                   self.video_current_time() - 2)
        if video_end_test_duration >= WAIT_TIMEOUT_S:
            self._driver.execute_script(
                'player.seekTo(%d, true)' % (self._video_duration - 2))
            self.wait_for_player_state(PLAYER_ENDED_STATE)
        else:
            raise error.TestError(
                'Test video is not long enough for the video end test.')
        # Verifying seek back from the end position.
        self._driver.execute_script('player.seekTo(%d, true)'
                                    % (self._video_duration / 2))
        self.wait_for_player_state(PLAYER_PLAYING_STATE)
        # So the playback doesn't stay at the mid.
        time.sleep(1)
        seek_position = self.video_current_time()
        if not (seek_position > self._video_duration / 2
            and seek_position < self._video_duration):
            raise error.TestError(
                'Seek location is wrong. Video length: %d, seek position: %d' %
                (self._video_duration, seek_position))

    def run_once(self):
        self._driver.get('http://localhost:8000/youtube5.html')

        # Verify that we are not in the Flash YouTube mode.
        child_processes = self.pyauto.GetBrowserInfo()['child_processes']
        flash_processes = [x for x in child_processes if
                           x['name'] == 'Shockwave Flash']
        if flash_processes:
            raise error.TestFail('Running YouTube in Flash mode.')

        # Waiting for test video to load.
        self.wait_for_player_state(PLAYER_PLAYING_STATE)
        self._driver.execute_script('player.setVolume(0)')
        self._video_duration = self.get_video_duration()
        self.verify_video_playback()
        self.verify_video_resolutions()
        self.verify_player_states()
