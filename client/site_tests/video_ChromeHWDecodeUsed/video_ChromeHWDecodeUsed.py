# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.video import histogram_verifier
from autotest_lib.client.cros.video import vda_constants


class video_ChromeHWDecodeUsed(test.test):
    """This test verifies VDA works in Chrome."""
    version = 1


    def run_once(self, video_file):
        """Tests whether VDA works by verifying histogram for the loaded video.

        @param video_file: Sample video file to be loaded in Chrome.
        """

        # TODO(hshi): Remove this once hw decode hang issue is fixed on sandybridge.
        # See http://crbug.com/521249.
        if utils.get_board() in ['lumpy', 'stumpy', 'parrot', 'butterfly']:
            return

        with chrome.Chrome() as cr:
            tab1 = cr.browser.tabs[0]
            tab1.Navigate(video_file)
            tab1.WaitForDocumentReadyStateToBeComplete()
            # Running the test longer to check errors and longer playback for
            # MSE videos.
            time.sleep(30)

            # Waits for histogram updated for the test video.
            histogram_verifier.verify(
                    cr,
                    vda_constants.MEDIA_GVD_INIT_STATUS,
                    vda_constants.MEDIA_GVD_BUCKET)
