# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
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
from autotest_lib.client.cros import power_status, power_utils
from autotest_lib.client.cros import service_stopper


# Chrome flags to use fake camera and skip camera permission.
EXTRA_BROWSER_ARGS = ['--use-fake-device-for-media-stream',
                      '--use-fake-ui-for-media-stream']
NO_WEBRTC_HARDWARE_ACCELERATION_BROWSER_ARGS = ['--disable-webrtc-hw-decoding',
                                                '--disable-webrtc-hw-encoding']

FAKE_FILE_ARG = '--use-file-for-fake-video-capture="%s"'
DOWNLOAD_BASE = 'http://commondatastorage.googleapis.com/chromiumos-test-assets-public/crowd/'
VIDEO_NAME = 'crowd720_25frames.y4m'

WEBRTC_INTERNALS_URL = 'chrome://webrtc-internals'
RTC_INIT_HISTOGRAM = 'Media.RTCVideoDecoderInitDecodeSuccess'
HISTOGRAMS_URL = 'chrome://histograms/' + RTC_INIT_HISTOGRAM

# Minimum battery charge percentage we prefer to run the test
BATTERY_INITIAL_CHARGED_MIN = 30

WEBRTC_WITH_HARDWARE_ACCELERATION = 'webrtc_with_hardware_acceleration'
WEBRTC_WITHOUT_HARDWARE_ACCELERATION = 'webrtc_without_hardware_acceleration'

# Measure duration in seconds
MEASURE_DURATION = 120
# Time to exclude from calculation after firing a task [seconds].
STABILIZATION_DURATION = 5

class video_WebRtcPower(test.test):
    """The test outputs the power consumption for WebRTC to performance
    dashboard.
    """
    version = 1

    def initialize(self):
        # Objects that need to be taken care of in cleanup() are initialized
        # here to None. Otherwise we run the risk of AttributeError raised in
        # cleanup() masking a real error that caused the test to fail during
        # initialize() before those variables were assigned.
        self._backlight = None

        self._services = service_stopper.ServiceStopper(
            service_stopper.ServiceStopper.POWER_DRAW_SERVICES)
        self._services.stop_services()

        self._power_status = power_status.get_status()
        # Verify that we are running on battery and the battery is
        # sufficiently charged.
        self._power_status.assert_battery_state(BATTERY_INITIAL_CHARGED_MIN)


    def start_loopback(self, cr):
        """
        Opens WebRTC loopback page.

        @param cr: Autotest Chrome instance.
        """
        tab = cr.browser.tabs[0]
        tab.Navigate(cr.browser.http_server.UrlOf(
                os.path.join(self.bindir, 'loopback.html')))
        tab.WaitForDocumentReadyStateToBeComplete()


    def assert_hardware_accelerated(self, cr, is_hardware_accelerated):
        """
        Checks if WebRTC decoding is hardware accelerated.

        @param cr: Autotest Chrome instance.
        @param is_hardware_accelerated: if is_hardware_accelerated is True then
        assert hardware accelerated otherwise assert hardware not accelerated.

        @raises error.TestError if decoding is not hardware accelerated while
        is_hardware_accelerated is True or if decoding is hardware accelerated
        while is_hardware_accelerated is False.
        """
        tab = cr.browser.tabs.New()
        def histograms_loaded():
            """Returns true if histogram is loaded."""
            tab.Navigate(HISTOGRAMS_URL)
            tab.WaitForDocumentReadyStateToBeComplete()
            return tab.EvaluateJavaScript(
                    'document.documentElement.innerText.search("%s") != -1'
                    % RTC_INIT_HISTOGRAM)

        if is_hardware_accelerated:
            utils.poll_for_condition(
                    histograms_loaded,
                    timeout=5,
                    exception=error.TestError(
                            'Cannot find rtc video decoder histogram.'),
                    sleep_interval=1)

            if tab.EvaluateJavaScript(
                    'document.documentElement.innerText.search('
                    '"1 = 100.0%") == -1'):
                raise error.TestError(
                        'Video decode acceleration is not working.')
        else:
            time.sleep(5)
            if histograms_loaded():
                raise error.TestError(
                        'Video decode acceleration should not be working.')

        tab.Close()


    def run_once(self):
        # Download test video.
        url = DOWNLOAD_BASE + VIDEO_NAME
        local_path = os.path.join(self.bindir, VIDEO_NAME)
        self.download_file(url, local_path)

        self._backlight = power_utils.Backlight()
        self._backlight.set_default()

        measurements = [power_status.SystemPower(
                self._power_status.battery_path)]
        self._power_logger = power_status.PowerLogger(measurements)
        self._power_logger.start()

        # Run the WebRTC tests.
        self.test_webrtc(local_path)

        keyvals = self._power_logger.calc()
        measurement_type = '_' + measurements[0].domain + '_pwr'
        energy_rate_with_hw = keyvals[WEBRTC_WITH_HARDWARE_ACCELERATION +
                                      measurement_type]
        self.output_perf_value(
                description='webrtc_energy_rate.mean',
                value=energy_rate_with_hw,
                units='W', higher_is_better=False)
        # Save the results to the autotest results directory
        self._power_logger.save_results(self.resultsdir)

        # Find the energy of full battery
        batinfo = self._power_status.battery[0]
        self.energy_full_design = batinfo.energy_full_design
        logging.info("energy_full_design = %0.3f Wh",
                     self.energy_full_design)

        logging.info('Expected battery life using WebRtc with'
                     'hardware acceleration : %0.3f hours',
                     self.energy_full_design / energy_rate_with_hw)

        energy_rate_without_hw = keyvals[WEBRTC_WITHOUT_HARDWARE_ACCELERATION +
                                         measurement_type]
        logging.info('Expected battery life using WebRtc without'
                     'hardware acceleration : %0.3f hours',
                     self.energy_full_design / energy_rate_without_hw)


    def test_webrtc(self, local_path):
        """
        Runs the WebRTC test with and without hardware acceleration.

        @param local_path: the path to the video file.
        @param test_duration: test duration for a run (seconds).
        """
        EXTRA_BROWSER_ARGS.append(FAKE_FILE_ARG % local_path)
        with chrome.Chrome(extra_browser_args=EXTRA_BROWSER_ARGS) as cr:
            # Open WebRTC loopback page.
            cr.browser.SetHTTPServerDirectories(self.bindir)
            self.start_loopback(cr)

            # Make sure decode is hardware accelerated.
            self.assert_hardware_accelerated(cr, True)

            # Record the start time and the end time of this power
            # measurement test run.
            time.sleep(STABILIZATION_DURATION)
            start_time = time.time()
            time.sleep(MEASURE_DURATION)
            self._power_logger.checkpoint(WEBRTC_WITH_HARDWARE_ACCELERATION,
                                          start_time)

        # Start chrome with test flag
        # and disabled WebRTC hardware encode and decode flag.
        with chrome.Chrome(extra_browser_args=EXTRA_BROWSER_ARGS +
                           NO_WEBRTC_HARDWARE_ACCELERATION_BROWSER_ARGS) as cr:

            # Open WebRTC loopback page.
            cr.browser.SetHTTPServerDirectories(self.bindir)
            self.start_loopback(cr)

            # Make sure decode is not hardware accelerated.
            self.assert_hardware_accelerated(cr, False)

            # Record the start time and the end time of this power
            # measurement test run.
            time.sleep(STABILIZATION_DURATION)
            start_time = time.time()
            time.sleep(MEASURE_DURATION)
            self._power_logger.checkpoint(WEBRTC_WITHOUT_HARDWARE_ACCELERATION,
                                          start_time)


    def download_file(self, url, local_path):
        """
        Downloads a file from the specified URL.

        @param url: URL of the file.
        @param local_path: the path that the file will be saved to.
        """
        logging.info('Downloading "%s" to "%s"', url, local_path)
        with closing(urllib2.urlopen(url)) as r, open(local_path, 'wb') as w:
            w.write(r.read())


    def cleanup(self):
        # cleanup() is run by common_lib/test.py.
        if self._backlight:
            self._backlight.restore()
        if self._services:
            self._services.restore_services()

        super(video_WebRtcPower, self).cleanup()
