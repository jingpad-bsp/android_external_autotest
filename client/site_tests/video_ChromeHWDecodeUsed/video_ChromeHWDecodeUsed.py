# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.video import histogram_parser


MEDIA_GVD_INIT_STATUS = 'Media.GpuVideoDecoderInitializeStatus'
MEDIA_GVD_BUCKET = 0


class video_ChromeHWDecodeUsed(test.test):
    """This test verifies VDA works in Chrome."""
    version = 1


    def run_once(self, video_file):
        """Tests whether VDA works by verifying histogram for the loaded video.

        @param video_file: Sample video file to be loaded in Chrome.
        """
        with chrome.Chrome() as cr:
            tab1 = cr.browser.tabs[0]
            tab1.Navigate(video_file)
            tab1.WaitForDocumentReadyStateToBeComplete()

            # Waits for histogram updated for the test video.
            parser = histogram_parser.HistogramParser(cr, MEDIA_GVD_INIT_STATUS)

            buckets = parser.buckets

            if (not buckets or not buckets[MEDIA_GVD_BUCKET]
                    or buckets[MEDIA_GVD_BUCKET].percent < 100.0):

                raise error.TestError('%s not found or not at 100 percent. %s'
                                      % MEDIA_GVD_BUCKET, str(parser))