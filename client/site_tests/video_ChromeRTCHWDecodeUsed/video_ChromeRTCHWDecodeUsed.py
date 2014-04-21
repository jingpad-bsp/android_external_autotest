# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from contextlib import closing
import logging
import os
import re
import time
import urllib2

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome


# Chrome flags to use fake camera and skip camera permission.
EXTRA_BROWSER_ARGS = ['--use-fake-device-for-media-stream',
                      '--use-fake-ui-for-media-stream']
FAKE_FILE_ARG = '--use-file-for-fake-video-capture="%s"'
DOWNLOAD_BASE = 'http://commondatastorage.googleapis.com/chromiumos-test-assets-public/crowd/'
VIDEO_NAME = 'crowd720_25frames.y4m'

RTC_VIDEO_DECODE = 'Media.RTCVideoDecoderInitDecodeSucces'
RTC_VIDEO_DECODE_BUCKET = 1
HISTOGRAMS_URL = 'chrome://histograms/'

class video_ChromeRTCHWDecodeUsed(test.test):
    """The test verifies HW Encoding for WebRTC video."""
    version = 1


    def start_loopback(self, cr):
        """
        Opens WebRTC loopback page.

        @param cr: Autotest Chrome instance.
        """
        tab = cr.browser.tabs[0]
        tab.Navigate(cr.browser.http_server.UrlOf(
                os.path.join(self.bindir, 'loopback.html')))
        tab.WaitForDocumentReadyStateToBeComplete()


    def assert_hardware_accelerated(self, cr):
        """
        Checks if WebRTC decoding is hardware accelerated.

        @param cr: Autotest Chrome instance.

        @raises error.TestError if decoding is not hardware accelerated.
        """
        tab = cr.browser.tabs.New()
        def histograms_loaded(histogram):
            """Returns true if histogram is loaded."""
            tab.Navigate(HISTOGRAMS_URL + histogram)
            tab.WaitForDocumentReadyStateToBeComplete()
            return tab.EvaluateJavaScript(
                    'document.documentElement.innerText.search("%s") != -1'
                    % histogram)

        def histogram_sucess(histogram, bucket):
            lines = tab.EvaluateJavaScript('document.documentElement.innerText')
            logging.info(lines)
            re_string = '^'+ str(bucket) +'\s\s-(.*)100.0%(.*)'
            if not re.findall(re_string, lines, re.MULTILINE):
                raise error.TestError(
                        '{0} didn\'t show up or is not 100%'
                        ' successful.'.format(histogram))

        utils.poll_for_condition(
                lambda: histograms_loaded(RTC_VIDEO_DECODE),
                timeout=5,
                exception=error.TestError('Cannot find %s histogram.',
                                          RTC_VIDEO_DECODE),
                sleep_interval=1)
        histogram_sucess(RTC_VIDEO_DECODE, RTC_VIDEO_DECODE_BUCKET)


    def run_once(self):
        # Download test video.
        url = DOWNLOAD_BASE + VIDEO_NAME
        local_path = os.path.join(self.bindir, VIDEO_NAME)
        self.download_file(url, local_path)

        # Start chrome with test flags.
        EXTRA_BROWSER_ARGS.append(FAKE_FILE_ARG % local_path)
        with chrome.Chrome(extra_browser_args=EXTRA_BROWSER_ARGS) as cr:
            # Open WebRTC loopback page.
            cr.browser.SetHTTPServerDirectories(self.bindir)
            self.start_loopback(cr)

            # Make sure decode is hardware accelerated.
            self.assert_hardware_accelerated(cr)


    def download_file(self, url, local_path):
        """
        Downloads a file from the specified URL.

        @param url: URL of the file.
        @param local_path: the path that the file will be saved to.
        """
        logging.info('Downloading "%s" to "%s"', url, local_path)
        with closing(urllib2.urlopen(url)) as r, open(local_path, 'wb') as w:
            w.write(r.read())
