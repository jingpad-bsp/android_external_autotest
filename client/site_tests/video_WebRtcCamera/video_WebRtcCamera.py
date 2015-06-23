# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome

# local import
import webcam

EXTRA_BROWSER_ARGS = ['--use-fake-ui-for-media-stream']

# Statistics from the loopback.html page.
TEST_PROGRESS = 'testProgress'

# Polling timeout
TIMEOUT = 240

# max number of allowed blackframes or frozen frames
BLACK_FRAMES_THRESHOLD = 10
FROZEN_FRAMES_THRESHOLD = 10

class video_WebRtcCamera(test.test):
    """Local Peer connection test with webcam at 720p."""
    version = 1

    def start_loopback(self, cr):
        """Opens WebRTC loopback page.

        @param cr: Autotest Chrome instance.
        """
        cr.browser.SetHTTPServerDirectories(self.bindir)

        self.tab = cr.browser.tabs[0]
        self.tab.Navigate(cr.browser.http_server.UrlOf(
                os.path.join(self.bindir, 'loopback.html')))
        self.tab.WaitForDocumentReadyStateToBeComplete()


    def is_test_completed(self):
        """Checks if WebRTC peerconnection test is done.

        @returns True if test complete, False otherwise.

        """
        def test_done():
          """Check the testProgress variable in HTML page."""

          # Wait for test completion on web page.
          test_progress = self.tab.EvaluateJavaScript(TEST_PROGRESS)
          return test_progress == 1

        try:
            utils.poll_for_condition(
                    test_done, timeout=TIMEOUT,
                    exception=error.TestError(
                        'Cannot find testProgress value.'),
                    sleep_interval=1)
        except error.TestError:
            partial_results = self.tab.EvaluateJavaScript('getResults()')
            logging.info('Here are the partial results so far: %s',
                         partial_results)
            return False
        else:
            return True


    def run_once(self):
        """Runs the video_WebRtcPeerConnectionWithCamera test."""
        self.board = utils.get_current_board()
        with chrome.Chrome(extra_browser_args=EXTRA_BROWSER_ARGS) as cr:
            # Open WebRTC loopback page and start the loopback.
            self.start_loopback(cr)
            if not self.check_loopback_result():
                raise error.TestFail('Failed webrtc camera test')


    def check_loopback_result(self):
        """Get the WebRTC Camera results."""
        if not self.is_test_completed():
            logging.error('loopback.html did not complete')
            return False
        try:
            results = self.tab.EvaluateJavaScript('getResults()')
        except:
            logging.error('Cannot retrieve results from loopback.html page')
            return False
        logging.info('Results: %s', results)
        for resolution in results:
            item = results[resolution]
            if (item['cameraErrors'] and resolution == '1280,720'
                    and webcam.supports_720p()):
                logging.error('Camera error: %s', item['cameraErrors'])
                return False
            if not item['frameStats']:
                output_resolution = re.sub(',', 'x', resolution)
                logging.error('Frame Stats is empty for resolution: %s',
                              output_resolution)
                return False

            if item['frameStats']['numBlackFrames'] > BLACK_FRAMES_THRESHOLD:
                logging.error('BlackFrames threshold overreach: '
                              'got %s > %s allowed',
                              item['frameStats']['numBlackFrames'],
                              BLACK_FRAMES_THRESHOLD)
                return False
            if item['frameStats']['numFrozenFrames'] > FROZEN_FRAMES_THRESHOLD:
                logging.error('FrozenFrames threshold overreach: '
                              'got %s > %s allowed',
                              item['frameStats']['numFrozenFrames'],
                              FROZEN_FRAMES_THRESHOLD)
                return False
            if item['frameStats']['numFrames'] == 0:
                logging.error('%s Frames were found',
                              item['frameStats']['numFrames'])
                return False

        return True
