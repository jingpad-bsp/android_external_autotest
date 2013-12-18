# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import sys_power


class power_FlashVideoSuspend(test.test):
    """Suspend the system with a video playing."""
    version = 1

    def run_once(self, video_urls=None):
        with chrome.Chrome() as cr:
            cr.browser.SetHTTPServerDirectories(self.bindir)
            tab = cr.browser.tabs[0]
            tab.Navigate(cr.browser.http_server.UrlOf(
                os.path.join(self.bindir, 'youtube.html')))
            self.suspend_with_youtube(cr.browser.tabs[0])


    def check_video_is_playing(self, tab):
        def get_current_time():
            return tab.EvaluateJavaScript('player.getCurrentTime()')

        old_time = get_current_time()
        utils.poll_for_condition(
            condition=lambda: get_current_time() > old_time,
            exception=error.TestError('Player is stuck until timeout.'))


    def suspend_with_youtube(self, tab):

        def player_is_ready():
            return tab.EvaluateJavaScript('player != undefined')

        utils.poll_for_condition(
            condition=player_is_ready,
            exception=error.TestError('Timeout wating player get ready.'))

        self.check_video_is_playing(tab)

        time.sleep(2)
        sys_power.kernel_suspend(10)
        time.sleep(2)

        self.check_video_is_playing(tab)
