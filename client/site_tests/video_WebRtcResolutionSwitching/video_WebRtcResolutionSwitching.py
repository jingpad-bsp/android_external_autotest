# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.common_lib.cros import webrtc_utils
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

    def start_test(self, cr, html_file):
        """Opens the test page.

        @param cr: Autotest Chrome instance.
        @param html_file: File object that contains the html to use for testing.
        """
        self.tab = cr.browser.tabs[0]
        self.tab.Navigate(cr.browser.platform.http_server.UrlOf(
                html_file.name))
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
            own_script_path = os.path.join(
                    self.bindir, 'resolution-switching.js')
            loopback_script_path = webrtc_utils.get_common_script_path(
                    'loopback-peerconnection.js')

            # Create the URLs to the JS scripts to include in the html file.
            # Normally we would use the http_server.UrlOf method. However,
            # that requires starting the server first. The server reads
            # all file contents on startup, meaning we must completely
            # create the html file first. Hence we create the url
            # paths relative to self.autodir which will be used as the
            # base of the server (implicitly since all files we use
            # share that path as a base).
            own_script_url = own_script_path[len(self.autodir):]
            loopback_script_url = loopback_script_path[len(self.autodir):]

            html_file = webrtc_utils.create_temp_html_file(
                    'Resolution Switching',
                    self.tmpdir,
                    own_script_url,
                    loopback_script_url)
            # Don't bother deleting the html file, the autotest tmp dir will be
            # cleaned up by the autotest framework.
            cr.browser.platform.SetHTTPServerDirectories(
                [own_script_path, html_file.name, loopback_script_path])
            self.start_test(cr, html_file)
            self.wait_test_completed(TIMEOUT)
            self.verify_status_ok()

    def verify_status_ok(self):
        """Verifies that the status of the test is 'ok-done'.

        @raises TestError the status is different from 'ok-done'
        """
        status = self.tab.EvaluateJavaScript('testRunner.getStatus()')
        if status != 'ok-done':
            raise error.TestFail('Failed: %s' % status)

