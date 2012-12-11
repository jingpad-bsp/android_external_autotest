# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, urllib, time

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, httpd

_WAIT_TIMEOUT = 5
_PLAYBACK_TEST_TIME = 5
_MEDIA_SUPPORT_AVAILABLE = 'maybe'

class desktopui_VideoSanity(cros_ui_test.UITest):
    version = 1


    def initialize(self):
        super(desktopui_VideoSanity, self).initialize('$default')
        self._driver = self.pyauto.NewWebDriver()
        self._testServer = httpd.HTTPListener(8000, docroot=self.bindir)
        self._testServer.run()

    def run_once(self):
        # Verifying <video> support.
        video_containers = ('mp4', 'ogg', 'webm')
        self._driver.get('http://localhost:8000/video.html')
        for container in video_containers:
            logging.info('Verifying video support for %s.' % container)
            status = self._driver.execute_script("return document."+
                     "createElement('video').canPlayType('video/" +
                      container + "')")
            if status != _MEDIA_SUPPORT_AVAILABLE:
                raise error.TestError('No media support available for %s.'
                                       % container)
        # Waiting for test video to load.
        wait_time = 0 # seconds
        while float(self._driver.execute_script(
                    'return videoCurTime.innerHTML')) < 1.0:
            time.sleep(1)
            wait_time = wait_time + 1
            if wait_time > _WAIT_TIMEOUT:
                raise error.TestError('Video failed to load.')
        # Muting the video.
        self._driver.execute_script('testvideo.volume=0')

        # Verifying video playback.
        playback = 0 # seconds
        prev_playback = 0
        while self.video_current_time() < self.video_duration() \
               and playback < _PLAYBACK_TEST_TIME:
            if self.video_current_time() <= prev_playback:
                raise error.TestError('Video is not playing.')
            prev_playback = self.video_current_time()
            time.sleep(1)
            playback = playback + 1

    def video_current_time(self):
        """Returns video's current playback time."""
        return int(self._driver.execute_script('return testvideo.currentTime'))

    def video_duration(self):
        """Returns video total length."""
        return int(self._driver.execute_script('return testvideo.duration'))
