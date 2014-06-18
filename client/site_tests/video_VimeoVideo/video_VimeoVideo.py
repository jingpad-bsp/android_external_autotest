# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome

import os
import time


class video_VimeoVideo(test.test):
    """This test verifies Vimeo video.

    - verify video playback.
    - verify player states.

    """
    version = 1
    _PLAYER_PLAY_STATE = 'play'
    _PLAYER_PAUSE_STATE = 'pause'
    _PLAYBACK_TEST_TIME_S = 10
    _WAIT_TIMEOUT_S = 10


    def _get_player_status(self):
        """Returns the player status."""
        return self._tab.EvaluateJavaScript('vimeo_player.status')


    def _wait_for_player(self):
        """Wait for the player to load."""
        self._tab.WaitForJavaScriptExpression(
                'typeof vimeo_player !== \'undefined\'', self._WAIT_TIMEOUT_S)

    def _wait_for_player_status(self, expected_status):
        """"Wait for expected player status.

        @param expected_status: expected player status to wait for.
        """
        utils.poll_for_condition(
                lambda: self._get_player_status() == expected_status,
                exception=error.TestError(
                        'Vimeo player failed to obtain %s status. '
                        'Current player status is %s.' %
                        (expected_status, self._get_player_status())),
                timeout=self._WAIT_TIMEOUT_S,
                sleep_interval=1)


    def _video_current_time(self):
        "Returns current video time."""
        self._tab.WaitForJavaScriptExpression(
                'typeof vimeo_player.duration == \'number\'',
                self._WAIT_TIMEOUT_S)
        return float(self._tab.EvaluateJavaScript('vimeo_player.duration'))


    def run_vimeo_tests(self, browser):
        """Run Vimeo video sanity tests.

        @param browser: The Browser object to run the test with.

        """
        self._tab = browser.tabs[0]
        self._tab.Navigate(browser.http_server.UrlOf(
                os.path.join(self.bindir, 'vimeo.html')))
        self._wait_for_player()
        self._wait_for_player_status(self._PLAYER_PLAY_STATE)
        # Abort the test if video is not playing.
        utils.poll_for_condition(
                lambda: self._video_current_time() > 5.0,
                exception=error.TestError(
                        'Init: video isn\'t playing.'),
                timeout=self._WAIT_TIMEOUT_S,
                sleep_interval=1)

        # Verify that Vimeo is playing the video in html5 mode.
        prc = utils.get_process_list('chrome', '--type=ppapi')
        if prc:
            raise error.TestFail('Vimeo is playing the video in Flash mode.')

        self._tab.ExecuteJavaScript('pause.click()')
        self._wait_for_player_status(self._PLAYER_PAUSE_STATE)
        time.sleep(1)

        # Verifying video playback.
        self._tab.ExecuteJavaScript('play.click()')
        self._wait_for_player_status(self._PLAYER_PLAY_STATE)
        playback = 0 # seconds
        prev_playback = 0
        while (playback < self._PLAYBACK_TEST_TIME_S):
            if self._video_current_time() <= prev_playback:
                utils.poll_for_condition(
                        lambda: self._video_current_time() > prev_playback,
                        exception=error.TestError(
                                'Long Wait: Video is not playing.'),
                        timeout=self._WAIT_TIMEOUT_S,
                        sleep_interval=1)
            prev_playback = self._video_current_time()
            time.sleep(1)
            playback = playback + 1


    def run_once(self):
        with chrome.Chrome() as cr:
            cr.browser.SetHTTPServerDirectories(self.bindir)
            self.run_vimeo_tests(cr.browser)
