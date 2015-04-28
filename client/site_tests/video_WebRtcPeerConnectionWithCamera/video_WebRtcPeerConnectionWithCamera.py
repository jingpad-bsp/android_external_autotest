# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome

EXTRA_BROWSER_ARGS = ['--use-fake-ui-for-media-stream']

# Statistics from the loopback.html page.
TEST_PROGRESS = 'testProgress'

# Polling timeout
TIMEOUT = 90


class video_WebRtcPeerConnectionWithCamera(test.test):
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

          # Wait for test completion on web page
          test_progress = self.tab.EvaluateJavaScript(TEST_PROGRESS)
          return test_progress == 1

        try:
            utils.poll_for_condition(
                    test_done, timeout=TIMEOUT,
                    exception=error.TestError('Cannot find testProgress value.'),
                    sleep_interval=1)
        except error.TestError:
            return False
        else:
            return True


    def run_once(self):
        """Runs the video_WebRtcPeerConnectionWithCamera test."""
        with chrome.Chrome(extra_browser_args=EXTRA_BROWSER_ARGS) as cr:
            # Open WebRTC loopback page and start the loopback.
            self.start_loopback(cr)
            if not self.check_loopback_result():
                raise error.TestFail('Failed 720p local peer connection test')


    def check_loopback_result(self):
        """Get the WebRTC Peerconnection loopback results."""
        if not self.is_test_completed():
            logging.error('loopback.html did not complete')
            return False
        try:
            results = self.tab.EvaluateJavaScript('getResults()')
        except:
            logging.error('Cannot retrieve results from loopback.html page')
            return False
        logging.info('Camera Type: %s', results['cameraType'])
        logging.info('Camera Errors: %s', results['cameraErrors'])
        logging.info('PeerConnectionstats: %s',
                     results['peerConnectionStats'])
        logging.info('FrameStats: %s', results['frameStats'])
        if results['cameraErrors']:
            logging.error('Camera error: %s', results['cameraErrors'])
            return False
        if not results['peerConnectionStats']:
            logging.info('Peer Connection Stats is empty')
            return False
        if results['peerConnectionStats'][1] == 0:
            logging.error('Max Input FPS is zero')
            return False
        if results['peerConnectionStats'][4] == 0:
            logging.error('Max Sent FPS is zero')
            return False
        if not results['frameStats']:
            logging.error('Frame Stats is empty')
            return False
        if results['frameStats']['numBlackFrames'] != 0:
            logging.error('%s Black Frames were found',
                          results['frameStats']['numBlackFrames'])
            return False
        if results['frameStats']['numFrozenFrames'] != 0:
            logging.error('%s Frozen Frames were found',
                          results['frameStats']['numFrozenFrames'])
            return False
        if results['frameStats']['numFrames'] == 0:
            logging.error('%s Frames were found', results['frameStats']['numFrames'])
            return False
        return True