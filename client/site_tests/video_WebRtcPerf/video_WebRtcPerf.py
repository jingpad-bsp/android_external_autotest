# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from contextlib import closing
import logging
import os
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

WEBRTC_INTERNALS_URL = 'chrome://webrtc-internals'
RTC_INIT_HISTOGRAM = 'Media.RTCVideoDecoderInitDecodeSuccess'
HISTOGRAMS_URL = 'chrome://histograms/' + RTC_INIT_HISTOGRAM

# These are the variable names in WebRTC internals.
# Maximum decode time of the frames of the last 10 seconds.
GOOG_MAX_DECODE_MS = 'googMaxDecodeMs'
# The decode time of the last frame.
GOOG_DECODE_MS = 'googDecodeMs'

# Javascript function to get the decode time. addStats is a function called by
# Chrome to pass WebRTC statistics every second.
ADD_STATS_JAVASCRIPT = (
        'var googMaxDecodeMs = new Array();'
        'var googDecodeMs = new Array();'
        'addStats = function(data) {'
        '  reports = data.reports;'
        '  for (var i=0; i < reports.length; i++) {'
        '    if (reports[i].type == "ssrc") {'
        '      values = reports[i].stats.values;'
        '      for (var j=0; j < values.length; j++) {'
        '        if (values[j] == "googMaxDecodeMs")'
        '          googMaxDecodeMs[googMaxDecodeMs.length] = values[j+1];'
        '        else if (values[j] == "googDecodeMs")'
        '          googDecodeMs[googDecodeMs.length] = values[j+1];'
        '      }'
        '    }'
        '  }'
        '}')

# Measure the stats until getting 10 samples or exceeding 15 seconds. addStats
# is called once per second for now.
NUM_DECODE_TIME_SAMPLES = 10
TIMEOUT = 15

class video_WebRtcPerf(test.test):
    """The test outputs the decode time for WebRtc to performance
    dashboard.
    """
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
        def histograms_loaded():
            """Returns true if histogram is loaded."""
            tab.Navigate(HISTOGRAMS_URL)
            tab.WaitForDocumentReadyStateToBeComplete()
            return tab.EvaluateJavaScript(
                    'document.documentElement.innerText.search("%s") != -1'
                    % RTC_INIT_HISTOGRAM)

        utils.poll_for_condition(
                histograms_loaded,
                timeout=5,
                exception=error.TestError(
                        'Cannot find rtc video decoder histogram.'),
                sleep_interval=1)
        if tab.EvaluateJavaScript(
                'document.documentElement.innerText.search('
                '"1 = 100.0%") == -1'):
            raise error.TestError('Video decode acceleration not working.')


    def open_stats_page(self, cr):
        """
        Opens WebRTC internal statistics page.

        @param cr: Autotest Chrome instance.

        @returns the tab of the stats page.
        """
        tab = cr.browser.tabs.New()
        tab.Navigate(WEBRTC_INTERNALS_URL)
        tab.WaitForDocumentReadyStateToBeComplete()
        # Inject stats callback function.
        tab.EvaluateJavaScript(ADD_STATS_JAVASCRIPT)
        return tab


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

            # Open WebRTC internals page for statistics.
            tab = self.open_stats_page(cr)

            # Collect the decode time until there are enough samples.
            start_time = time.time()
            max_decode_time_list = []
            decode_time_list = []
            while (time.time() - start_time < TIMEOUT and
                   len(decode_time_list) < NUM_DECODE_TIME_SAMPLES):
                time.sleep(1)
                max_decode_time_list = []
                decode_time_list = []
                try:
                    max_decode_time_list = [int(x) for x in
                            tab.EvaluateJavaScript(GOOG_MAX_DECODE_MS)]
                    decode_time_list = [int(x) for x in
                            tab.EvaluateJavaScript(GOOG_DECODE_MS)]
                except:
                    pass

            # Output the values if they are valid.
            if len(max_decode_time_list) < NUM_DECODE_TIME_SAMPLES:
                raise error.TestError('Not enough ' + GOOG_MAX_DECODE_MS)
            if len(decode_time_list) < NUM_DECODE_TIME_SAMPLES:
                raise error.TestError('Not enough ' + GOOG_DECODE_MS)
            max_decode_time = max(max_decode_time_list)
            decode_time_median = self.get_median(decode_time_list)
            logging.info("Max decode time list=%s", str(max_decode_time_list))
            logging.info("Decode time list=%s", str(decode_time_list))
            logging.info("Maximum decode time=%d, median=%d", max_decode_time,
                         decode_time_median)
            self.output_perf_value(
                    description="decode_time.max", value=max_decode_time,
                    units="milliseconds", higher_is_better=False)
            self.output_perf_value(
                    description="decode_time.percentile_0.50",
                    value=decode_time_median,
                    units="milliseconds", higher_is_better=False)


    def get_median(self, seq):
        """
        Calculates the median of a sequence of numbers.

        @param seq: a list with numbers.

        @returns the median of the numbers.
        """
        seq.sort()
        size = len(seq)
        if size % 2 != 0:
            return seq[size / 2]
        return (seq[size / 2] + seq[size / 2 - 1]) / 2.0


    def download_file(self, url, local_path):
        """
        Downloads a file from the specified URL.

        @param url: URL of the file.
        @param local_path: the path that the file will be saved to.
        """
        logging.info('Downloading "%s" to "%s"', url, local_path)
        with closing(urllib2.urlopen(url)) as r, open(local_path, 'wb') as w:
            w.write(r.read())
