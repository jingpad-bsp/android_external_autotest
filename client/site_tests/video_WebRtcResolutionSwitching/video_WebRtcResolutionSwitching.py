# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.video import helper_logger

EXTRA_BROWSER_ARGS = ['--use-fake-ui-for-media-stream',
                      '--use-fake-device-for-media-stream']

# Polling timeout.
TIMEOUT = 70

# The test's runtime.
TEST_RUNTIME_SECONDS = 60

# Number of peer connections to use.
NUM_PEER_CONNECTIONS = 5

# Delay between each iteration of changing resolutions.
ITERATION_DELAY_MILLIS = 300;


class video_WebRtcResolutionSwitching(test.test):
    """Tests multiple peerconnections that randomly change resolution."""
    version = 1

    def start_test(self, cr):
        """Opens the test page.

        @param cr: Autotest Chrome instance.
        """
        cr.browser.platform.SetHTTPServerDirectories(self.bindir)

        self.tab = cr.browser.tabs[0]
        self.tab.Navigate(cr.browser.platform.http_server.UrlOf(
                os.path.join(self.bindir, 'resolution-switching.html')))
        self.tab.WaitForDocumentReadyStateToBeComplete()
        self.tab.EvaluateJavaScript(
                "startTest(%d, %d, %d)" % (
                        TEST_RUNTIME_SECONDS,
                        NUM_PEER_CONNECTIONS,
                        ITERATION_DELAY_MILLIS))

    def wait_test_completed(self, timeout_secs):
        """Waits until the test is done.

        @param timeout_secs Max time to wait in seconds.

        @raises TestError on timeout, or javascript eval fails, or
                error status from the JS.
        """
        def _test_done():
            status = self.tab.EvaluateJavaScript('testRunner.getStatus()')
            if status == 'video-broken':
              raise error.TestFail('Video is broken')
            logging.debug(status)
            return status == 'ok-done'

        utils.poll_for_condition(
                _test_done, timeout=timeout_secs, sleep_interval=1,
                desc='test reports itself as finished')

    @helper_logger.video_log_wrapper
    def run_once(self):
        """Runs the test."""
        with chrome.Chrome(extra_browser_args = EXTRA_BROWSER_ARGS + \
                           [helper_logger.chrome_vmodule_flag()],
                           init_network_controller = True) as cr:
            self.start_test(cr)
            self.wait_test_completed(TIMEOUT)
            self.print_result()

    def print_result(self):
        """Prints results unless status is different from ok-done.

        @raises TestError if the test failed outright.
        """
        status = self.tab.EvaluateJavaScript('testRunner.getStatus()')
        if status != 'ok-done':
            raise error.TestFail('Failed: %s' % status)

        results = self.tab.EvaluateJavaScript('testRunner.getResults()')
        logging.info('runTimeSeconds: %.2f', results['runTimeSeconds'])

        self.output_perf_value(
                description='run_time',
                value=results['runTimeSeconds'],
                units='seconds')

