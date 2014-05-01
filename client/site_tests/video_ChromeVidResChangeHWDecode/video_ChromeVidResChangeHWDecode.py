# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome


MEDIA_GVD_INIT_STATUS = 'Media.GpuVideoDecoderInitializeStatus'


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
            tab2 = cr.browser.tabs.New()

            def search_histogram_text(text):
                """Searches the histogram text in the second tab.

                @param text: Text to be searched in the histogram tab.
                """
                return tab2.EvaluateJavaScript('document.documentElement && '
                         'document.documentElement.innerText.search('
                         '\'%s\') != -1' % text)

            def gpu_histogram_loaded():
                """Loads the histogram in the second tab."""
                tab2.Navigate('chrome://histograms/%s' % MEDIA_GVD_INIT_STATUS)
                return search_histogram_text(MEDIA_GVD_INIT_STATUS)

            utils.poll_for_condition(gpu_histogram_loaded,
                    exception=error.TestError(
                            'Histogram gpu status failed to load.'),
                            sleep_interval=1)
            if not search_histogram_text('average = 0.0'):
                raise error.TestError('Video decode acceleration not working.')

            # Verify the video playback.
            for i in range(1, video_len/2):
                if tab1.EvaluateJavaScript(
                        'testvideo.ended || testvideo.paused'):
                    raise error.TestError('Video either stopped or ended.')
                time.sleep(1)

            # Verify that video ends successfully.
            utils.poll_for_condition(
                    lambda: tab1.EvaluateJavaScript('testvideo.ended'),
                    timeout=video_len - video_len/2,
                    exception=error.TestError(
                            'Video didn\'t end successfully.'),
                    sleep_interval=1)
