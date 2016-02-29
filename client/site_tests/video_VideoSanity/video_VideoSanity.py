# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import shutil
import logging

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.video import constants
from autotest_lib.client.cros.video import native_html5_player


class video_VideoSanity(test.test):
    """This test verify the media elements and video sanity.

    - verify support for mp4, vp8 and vp9  media.
    - verify html5 video playback.

    """
    version = 2


    def run_once(self, video_file):
        """
        Tests whether the requested video is playable

        @param video_file: Sample video file to be played in Chrome.

        """
        boards_to_skip = ['x86-mario', 'x86-zgb']
        dut_board = utils.get_current_board()
        if dut_board in boards_to_skip:
            logging.info("Skipping test run on this board.")
            return
        with chrome.Chrome() as cr:
             shutil.copy2(constants.VIDEO_HTML_FILEPATH, self.bindir)
             video_path = os.path.join(constants.CROS_VIDEO_DIR,
                                       'files', video_file)
             shutil.copy2(video_path, self.bindir)
             cr.browser.platform.SetHTTPServerDirectories(self.bindir)
             tab = cr.browser.tabs[0]
             html_fullpath = os.path.join(self.bindir, 'video.html')
             url = cr.browser.platform.http_server.UrlOf(html_fullpath)

             player = native_html5_player.NativeHtml5Player(
                     tab,
                     full_url = url,
                     video_id = 'video',
                     video_src_path = video_file,
                     event_timeout = 120)
             player.load_video()
             player.play()
             player.verify_video_can_play(constants.PLAYBACK_TEST_TIME_S)
