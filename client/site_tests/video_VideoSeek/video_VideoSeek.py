# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome

WAIT_TIMEOUT_S = 180

class video_VideoSeek(test.test):
    """This test verifies video seek works in Chrome."""
    version = 1

    def run_once(self, video, fast_seek=False):
        """Tests whether video seek works by random seeks forward and backward.

        @param video: Sample video file to be seeked in Chrome.
        """
        with chrome.Chrome() as cr:
            cr.browser.SetHTTPServerDirectories(self.bindir)
            tab = cr.browser.tabs[0]
            tab.Navigate(cr.browser.http_server.UrlOf(
                    os.path.join(self.bindir, 'video.html')))
            tab.WaitForDocumentReadyStateToBeComplete()

            # Test seeks either before or after the previous seeks complete.
            seek_event = 'seeking' if fast_seek else 'seeked'
            tab.EvaluateJavaScript(
                'loadSourceAndRunSeekTest("%s", "%s")' % (video, seek_event))

            def get_seek_test_status():
                seek_test_status = tab.EvaluateJavaScript('getSeekTestStatus()')
                logging.info('Seeking: %s', seek_test_status)
                return seek_test_status

            utils.poll_for_condition(
                    lambda: get_seek_test_status() == 'pass',
                    exception=error.TestError('Seek test is stuck and timeout'),
                    timeout=WAIT_TIMEOUT_S,
                    sleep_interval=1)
