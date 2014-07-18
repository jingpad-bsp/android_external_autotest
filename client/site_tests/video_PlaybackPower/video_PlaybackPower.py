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
from autotest_lib.client.cros import power_status, power_utils
from autotest_lib.client.cros import service_stopper


DISABLE_ACCELERATED_VIDEO_DECODE_BROWSER_ARGS = [
        '--disable-accelerated-video-decode']
DOWNLOAD_BASE = 'http://commondatastorage.googleapis.com/chromeos-test-public/big_buck_bunny/'

GPU_VIDEO_INIT_HISTOGRAM = 'Media.GpuVideoDecoderInitializeStatus'
HISTOGRAMS_URL = 'chrome://histograms/' + GPU_VIDEO_INIT_HISTOGRAM

# Minimum battery charge percentage we prefer to run the test
BATTERY_INITIAL_CHARGED_MIN = 10

PLAYBACK_WITH_HW_ACCELERATION = 'playback_with_hw_acceleration'
PLAYBACK_WITHOUT_HW_ACCELERATION = 'playback_without_hw_acceleration'

# Measure duration in seconds
MEASURE_DURATION = 20
# Time to exclude from calculation after firing a task [seconds].
STABILIZATION_DURATION = 5

# The status code indicating GpuVideoDecoder::Initialize() has succeeded.
GPU_VIDEO_INIT_BUCKET = 0

class video_PlaybackPower(test.test):
    """
    The test outputs the power consumption for video playback to
    performance dashboard.
    """
    version = 1


    def initialize(self):
        # Objects that need to be taken care of in cleanup() are initialized
        # here. Otherwise we run the risk of AttributeError raised in
        # cleanup() masking a real error that caused the test to fail during
        # initialize() before those variables were assigned.
        self._backlight = power_utils.Backlight()
        self._backlight.set_default()

        self._services = service_stopper.ServiceStopper(
            service_stopper.ServiceStopper.POWER_DRAW_SERVICES)
        self._services.stop_services()

        self._power_status = power_status.get_status()
        # Verify that we are running on battery and the battery is
        # sufficiently charged.
        self._power_status.assert_battery_state(BATTERY_INITIAL_CHARGED_MIN)


    def start_playback(self, cr, local_path):
        """
        Opens the video and plays it.

        @param cr: Autotest Chrome instance.
        @param local_path: path to the local video file to play
        """
        tab = cr.browser.tabs[0]
        tab.Navigate(cr.browser.http_server.UrlOf(local_path))
        tab.WaitForDocumentReadyStateToBeComplete()


    def is_hardware_accelerated(self, cr):
        """
        Checks if video decoding is hardware accelerated.

        @param cr: Autotest Chrome instance.
        @return True if it is using hardware acceleration, False otherwise.
        """
        result = False
        tab = cr.browser.tabs.New()
        def histograms_loaded():
            """Returns true if histogram is loaded."""
            tab.Navigate(HISTOGRAMS_URL)
            tab.WaitForDocumentReadyStateToBeComplete()
            return tab.EvaluateJavaScript(
                    'document.documentElement.innerText.search("%s") != -1'
                    % GPU_VIDEO_INIT_HISTOGRAM)

        def histogram_success():
            """Returns true if GpuVideoDecoder::Initialize() has succeeded."""
            lines = tab.EvaluateJavaScript('document.documentElement.innerText')
            # Example of the expected string to match:
            # 0  --------------------------O (1 = 100.0%)
            re_string = '^'+ str(GPU_VIDEO_INIT_BUCKET) +'\s\s-.*100\.0%.*'
            return re.search(re_string, lines, re.MULTILINE) != None

        try:
            utils.poll_for_condition(
                    histograms_loaded,
                    timeout=5,
                    exception=error.TestError(
                            'Cannot find gpu video decoder histogram.'),
                    sleep_interval=1)
        except error.TestError:
            result = False
        else:
            result = histogram_success()

        tab.Close()
        return result


    def run_once(self, video_name, video_format):
        # Download test video.
        url = DOWNLOAD_BASE + video_name
        local_path = os.path.join(self.bindir, video_name)
        self.download_file(url, local_path)

        measurements = [power_status.SystemPower(
                self._power_status.battery_path)]
        self._power_logger = power_status.PowerLogger(measurements)
        self._power_logger.start()

        # Run the video playback tests.
        self.test_playback(local_path)

        keyvals = self._power_logger.calc()

        # Find the energy of full battery
        self.energy_full_design = (self._power_status.battery[0].
                                   energy_full_design)
        logging.info("energy_full_design = %0.3f Wh",
                     self.energy_full_design)

        measurement_type = '_' + measurements[0].domain + '_pwr'

        energy_rate_with_hw = keyvals.get(PLAYBACK_WITH_HW_ACCELERATION +
                                          measurement_type)
        if energy_rate_with_hw:
            self.output_perf_value(
                    description= 'hw_' + video_format +
                                 '_video_energy_rate.mean',
                    value=energy_rate_with_hw,
                    units='W', higher_is_better=False)

            logging.info('Expected battery life of playing the video with '
                         'hardware acceleration : %0.3f hours',
                         self.energy_full_design / energy_rate_with_hw)

        energy_rate_without_hw = keyvals[PLAYBACK_WITHOUT_HW_ACCELERATION +
                                         measurement_type]
        self.output_perf_value(
                description= 'sw_' + video_format + '_video_energy_rate.mean',
                value=energy_rate_without_hw,
                units='W', higher_is_better=False)
        logging.info('Expected battery life of playing the video without '
                     'hardware acceleration : %0.3f hours',
                     self.energy_full_design / energy_rate_without_hw)

        # Save the results to the autotest results directory
        self._power_logger.save_results(self.resultsdir)


    def test_playback(self, local_path):
        """
        Runs the video playback test with and without hardware acceleration.

        @param local_path: the path to the video file.
        """
        with chrome.Chrome() as cr:
            # Open video playback page.
            cr.browser.SetHTTPServerDirectories(self.bindir)
            self.start_playback(cr, local_path)

            # Record the start time and the end time of this power
            # measurement test run.
            time.sleep(STABILIZATION_DURATION)
            start_time = time.time()
            time.sleep(MEASURE_DURATION)
            end_time = time.time()

            # Check if decode is hardware accelerated.
            if self.is_hardware_accelerated(cr):
                self._power_logger.checkpoint(PLAYBACK_WITH_HW_ACCELERATION,
                                              start_time, end_time)
            else:
                logging.info("Can not use hardware decoding")
                self._power_logger.checkpoint(PLAYBACK_WITHOUT_HW_ACCELERATION,
                                              start_time, end_time)
                return

        # Start chrome with test flag
        # and disabled video hardware decode flag.
        with chrome.Chrome(extra_browser_args=
                DISABLE_ACCELERATED_VIDEO_DECODE_BROWSER_ARGS) as cr:

            # Open video playback page.
            cr.browser.SetHTTPServerDirectories(self.bindir)
            self.start_playback(cr, local_path)

            # Record the start time and the end time of this power
            # measurement test run.
            time.sleep(STABILIZATION_DURATION)
            start_time = time.time()
            time.sleep(MEASURE_DURATION)
            self._power_logger.checkpoint(PLAYBACK_WITHOUT_HW_ACCELERATION,
                                          start_time)
            # Make sure decode is not hardware accelerated.
            if self.is_hardware_accelerated(cr):
                raise error.TestError(
                        'Video decode acceleration should not be working.')


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

        super(video_PlaybackPower, self).cleanup()
