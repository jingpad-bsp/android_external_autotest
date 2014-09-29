# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.video import histogram_parser


MEDIA_GVD_INIT_STATUS = 'Media.GpuVideoDecoderInitializeStatus'
MEDIA_GVD_BUCKET = 0


class video_ChromeVidResChangeHWDecode(test.test):
    """Verify that VDA works in Chrome for video with resolution changes."""
    version = 1


    def run_once(self, video_file, video_len):
        """Verify VDA and playback for the video_file.

        @param video_file: test video file.
        """
        with chrome.Chrome() as cr:
            cr.browser.SetHTTPServerDirectories(self.bindir)
            tab1 = cr.browser.tabs[0]
            tab1.Navigate(cr.browser.http_server.UrlOf(
                    os.path.join(self.bindir, 'video.html')))
            tab1.WaitForDocumentReadyStateToBeComplete()
            tab1.EvaluateJavaScript(
                'loadVideo("%s")' % (video_file))

            # Waits for histogram updated for the test video.
            parser = histogram_parser.HistogramParser(cr.browser.tabs.New(),
                                                      MEDIA_GVD_INIT_STATUS)
            buckets = parser.buckets

            if (not buckets or not buckets[MEDIA_GVD_BUCKET]
                    or buckets[MEDIA_GVD_BUCKET].percent < 100.0):

                raise error.TestError('%s not found or not at 100 percent. %s'
                                      % MEDIA_GVD_BUCKET, str(parser))

            # Verify the video playback.
            for i in range(1, video_len/2):
                if tab1.EvaluateJavaScript(
                        'testvideo.ended || testvideo.paused'):
                    raise error.TestError('Video either stopped or ended.')
                time.sleep(1)

            # Verify that video ends successfully.
            utils.poll_for_condition(
                    lambda: tab1.EvaluateJavaScript('testvideo.ended'),
                    timeout=video_len,
                    exception=error.TestError('Video did not end successfully'),
                    sleep_interval=1)
