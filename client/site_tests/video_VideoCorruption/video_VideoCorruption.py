# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome

WAIT_TIMEOUT_S = 30

class video_VideoCorruption(test.test):
    """This test verifies playing corrupted video in Chrome."""
    version = 1

    def run_once(self, video):
        """Tests whether Chrome handles corrupted videos gracefully.

        @param video: Sample corrupted video file to be played in Chrome.
        """
        with chrome.Chrome() as cr:
            cr.browser.SetHTTPServerDirectories(self.bindir)
            tab = cr.browser.tabs[0]
            tab.Navigate(cr.browser.http_server.UrlOf(
                    os.path.join(self.bindir, 'video.html')))
            tab.WaitForDocumentReadyStateToBeComplete()

            tab.EvaluateJavaScript(
                    'loadSourceAndRunCorruptionTest("%s")' % video)

            # Expect corruption being detected after playing corrupted video.
            utils.poll_for_condition(
                    lambda: tab.EvaluateJavaScript('corruptionDetected()'),
                    exception=error.TestError('Corruption test is timeout'),
                    timeout=WAIT_TIMEOUT_S,
                    sleep_interval=1)
