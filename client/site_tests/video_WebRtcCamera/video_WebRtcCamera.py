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

EXTRA_BROWSER_ARGS = ['--use-fake-ui-for-media-stream']

# Statistics from the loopback.html page.
TEST_PROGRESS = 'testProgress'

# Polling timeout.
TIMEOUT = 240


class video_WebRtcCamera(test.test):
    """Local Peer connection test with webcam at 720p."""
    version = 1

    def start_loopback(self, cr):
        """Opens WebRTC loopback page.

        @param cr: Autotest Chrome instance.
        """
        cr.browser.platform.SetHTTPServerDirectories(self.bindir)

        self.tab = cr.browser.tabs[0]
        self.tab.Navigate(cr.browser.platform.http_server.UrlOf(
                os.path.join(self.bindir, 'loopback.html')))
        self.tab.WaitForDocumentReadyStateToBeComplete()


    def webcam_supports_720p(self):
        """Checks if 720p capture supported.

        @returns: True if 720p supported, false if VGA is supported.
        @raises: TestError if neither 720p nor VGA are supported.
        """
        cmd = 'lsusb -v'
        # Get usb devices and make output a string with no newline marker.
        usb_devices = utils.system_output(cmd, ignore_status=True).splitlines()
        usb_devices = ''.join(usb_devices)

        # Check if 720p resolution supported.
        if re.search(r'\s+wWidth\s+1280\s+wHeight\s+720', usb_devices):
            return True
        # The device should support at least VGA.
        # Otherwise the cam must be broken.
        if re.search(r'\s+wWidth\s+640\s+wHeight\s+480', usb_devices):
            return False
        # This should not happen.
        raise error.TestFail(
                'Could not find any cameras reporting '
                'either VGA or 720p in lsusb output: %s' % usb_devices)


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
            self.print_perf_results()


    def print_perf_results(self):
        """Prints the perf results unless there was an error.

        @returns the empty string if perf results were printed, otherwise
                 a description of the error that occured.
        """
        if not self.is_test_completed():
            raise error.TestFail('loopback.html did not complete')
        try:
            results = self.tab.EvaluateJavaScript('getResults()')
        except Exception as e:
            raise error.TestFail('Failed to get loopback.html results', e)
        logging.info('Results: %s', results)

        errors = []
        for width_height, data in results.iteritems():
            resolution = re.sub(',', 'x', width_height)
            if (data['cameraErrors'] and resolution == '1280x720'
                    and self.webcam_supports_720p()):
                errors.append('Camera error: %s for resolution '
                              '%s.' % (data['cameraErrors'], resolution))
                continue
            if not data['frameStats']:
                errors.append('Frame Stats is empty '
                              'for resolution: %s' % resolution)
                continue
            self.output_perf_value(
                    description='black_frames_%s' % resolution,
                    value=data['frameStats']['numBlackFrames'],
                    units='frames', higher_is_better=False)
            self.output_perf_value(
                    description='frozen_frames_%s' % resolution,
                    value=data['frameStats']['numFrozenFrames'],
                    units='frames', higher_is_better=False)
            self.output_perf_value(
                    description='total_num_frames_%s' % resolution,
                    value=data['frameStats']['numFrames'],
                    units='frames', higher_is_better=True)
        if errors:
            raise error.TestFail('Found errors: %s' % ', '.join(errors))
