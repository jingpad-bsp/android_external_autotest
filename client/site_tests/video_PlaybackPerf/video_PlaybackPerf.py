# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from contextlib import closing
import logging
import os
import re
import time
import urllib2

from autotest_lib.client.bin import site_utils, test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import service_stopper


DISABLE_ACCELERATED_VIDEO_DECODE_BROWSER_ARGS = [
        '--disable-accelerated-video-decode']
DOWNLOAD_BASE = 'http://commondatastorage.googleapis.com/chromiumos-test-assets-public/crowd/'

GPU_VIDEO_INIT_HISTOGRAM = 'Media.GpuVideoDecoderInitializeStatus'
HISTOGRAMS_URL = 'chrome://histograms/' + GPU_VIDEO_INIT_HISTOGRAM

PLAYBACK_WITH_HW_ACCELERATION = 'playback_with_hw_acceleration'
PLAYBACK_WITHOUT_HW_ACCELERATION = 'playback_without_hw_acceleration'

# Measurement duration in seconds.
MEASUREMENT_DURATION = 30
# Time to exclude from calculation after playing a video [seconds].
STABILIZATION_DURATION = 10

# The status code indicating GpuVideoDecoder::Initialize() has succeeded.
GPU_VIDEO_INIT_BUCKET = 0

# List of thermal throttling services that should be disabled.
# - temp_metrics for link.
# - thermal for daisy, snow, pit etc.
THERMAL_SERVICES = ['temp_metrics', 'thermal']

# Time in seconds to wait for cpu idle until giveup.
WAIT_FOR_IDLE_CPU_TIMEOUT = 60.0
# Maximum percent of cpu usage considered as idle.
CPU_IDLE_USAGE = 0.1

CPU_USAGE_DESCRIPTION = '_video_cpu_usage'
DROPPED_FRAMES_DESCRIPTION = '_video_dropped_frames'

class video_PlaybackPerf(test.test):
    """
    The test outputs the cpu usage and the dropped frame count for video playback
    to performance dashboard.
    """
    version = 1


    def initialize(self):
        self._service_stopper = None
        self._original_governors = None


    def start_playback(self, cr, local_path):
        """
        Opens the video and plays it.

        @param cr: Autotest Chrome instance.
        @param local_path: path to the local video file to play.
        """
        cr.browser.SetHTTPServerDirectories(self.bindir)

        tab = cr.browser.tabs[0]
        tab.Navigate(cr.browser.http_server.UrlOf(local_path))
        tab.WaitForDocumentReadyStateToBeComplete()
        tab.EvaluateJavaScript("document.getElementsByTagName('video')[0]."
                               "loop=true")


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


    def run_once(self, video_name, video_format,
                 assert_hardware_acceleration=True):
        # Download test video.
        url = DOWNLOAD_BASE + video_name
        local_path = os.path.join(self.bindir, video_name)
        self.download_file(url, local_path)

        # Run the video playback dropped frame tests.
        keyvals = self.test_dropped_frames(local_path, assert_hardware_acceleration)
        self.log_result(keyvals, DROPPED_FRAMES_DESCRIPTION + video_format,
                        'frames')

        # Run the video playback cpu usage tests.
        keyvals = self.test_cpu_usage(local_path, assert_hardware_acceleration)
        self.log_result(keyvals, CPU_USAGE_DESCRIPTION + video_format,
                        'percent')


    def test_dropped_frames(self, local_path, assert_hardware_acceleration):
        """
        Runs the video dropped frame test.

        @param local_path: the path to the video file.
        @param assert_hardware_acceleration: True if we want to raise an
                exception when hardware acceleration is not used,
                False otherwise.

        @return a dictionary that contains the test result.
        """
        def get_dropped_frames(cr):
            time.sleep(MEASUREMENT_DURATION)
            tab = cr.browser.tabs[0]
            return tab.EvaluateJavaScript("document.getElementsByTagName"
                                          "('video')[0].webkitDroppedFrameCount")
        return self.test_playback(local_path, assert_hardware_acceleration,
                                  get_dropped_frames)


    def test_cpu_usage(self, local_path, assert_hardware_acceleration):
        """
        Runs the video cpu usage test.

        @param local_path: the path to the video file.
        @param assert_hardware_acceleration: True if we want to raise error
                exception when it does not use hardware acceleration by
                default, False otherwise.

        @return a dictionary that contains the test result.
        """
        def get_cpu_usage(cr):
            time.sleep(STABILIZATION_DURATION)
            cpu_usage_start = site_utils.get_cpu_usage()
            time.sleep(MEASUREMENT_DURATION)
            cpu_usage_end = site_utils.get_cpu_usage()
            return site_utils.compute_active_cpu_time(cpu_usage_start,
                                                      cpu_usage_end) * 100

        if not utils.wait_for_idle_cpu(WAIT_FOR_IDLE_CPU_TIMEOUT,
                                       CPU_IDLE_USAGE):
            raise error.TestError('Could not get idle CPU.')
        if not utils.wait_for_cool_machine():
            raise error.TestError('Could not get cold machine.')
        # Stop the thermal service that may change the cpu frequency.
        self._service_stopper = service_stopper.ServiceStopper(THERMAL_SERVICES)
        # Set the scaling governor to performance mode to set the cpu to the
        # highest frequency available.
        self._original_governors = utils.set_high_performance_mode()
        return self.test_playback(local_path, assert_hardware_acceleration,
                                  get_cpu_usage)


    def test_playback(self, local_path, assert_hardware_acceleration,
                      gather_result):
        """
        Runs the video playback test with and without hardware acceleration.

        @param local_path: the path to the video file.
        @param assert_hardware_acceleration: True if we want to raise error
                exception when it does not use hardware acceleration by
                default, False otherwise.
        @param gather_result: a function to run and return the test result
                after chrome opens. The input parameter of the funciton is
                Autotest chrome instance.

        @return a dictionary that contains test the result.
        """
        keyvals = {}

        with chrome.Chrome() as cr:
            # Open the video playback page and start playing.
            self.start_playback(cr, local_path)
            result = gather_result(cr)

            # Check if decode is hardware accelerated.
            if self.is_hardware_accelerated(cr):
                keyvals[PLAYBACK_WITH_HW_ACCELERATION] = result
            else:
                if assert_hardware_acceleration:
                    raise error.TestError(
                            'Can not use hardware decoding.')
                else:
                    logging.info("Can not use hardware decoding.")
                keyvals[PLAYBACK_WITHOUT_HW_ACCELERATION] = result
                return keyvals

        # Start chrome with disabled video hardware decode flag.
        with chrome.Chrome(extra_browser_args=
                DISABLE_ACCELERATED_VIDEO_DECODE_BROWSER_ARGS) as cr:
            # Open the video playback page and start playing.
            self.start_playback(cr, local_path)
            result = gather_result(cr)

            # Make sure decode is not hardware accelerated.
            if self.is_hardware_accelerated(cr):
                raise error.TestError(
                        'Video decode acceleration should not be working.')
            keyvals[PLAYBACK_WITHOUT_HW_ACCELERATION] = result

        return keyvals


    def download_file(self, url, local_path):
        """
        Downloads a file from the specified URL.

        @param url: URL of the file.
        @param local_path: the path that the file will be saved to.
        """
        logging.info('Downloading "%s" to "%s"', url, local_path)
        with closing(urllib2.urlopen(url)) as r, open(local_path, 'wb') as w:
            w.write(r.read())


    def log_result(self, keyvals, description, units):
        """
        Logs the test result output to the performance dashboard.

        @param keyvals: a dictionary that contains results returned by
                test_playback.
        @param description: a string that describes the video format and test result.
        @param units: the units of test result.
        """
        result_with_hw = keyvals.get(PLAYBACK_WITH_HW_ACCELERATION)
        if result_with_hw is not None:
            self.output_perf_value(
                    description= 'hw_' + description, value=result_with_hw,
                    units=units, higher_is_better=False)

        result_without_hw = keyvals[PLAYBACK_WITHOUT_HW_ACCELERATION]
        self.output_perf_value(
                description= 'sw_' + description, value=result_without_hw,
                units=units, higher_is_better=False)


    def cleanup(self):
        # cleanup() is run by common_lib/test.py.
        if self._service_stopper:
            self._service_stopper.restore_services()
        if self._original_governors:
            utils.restore_scaling_governor_states(self._original_governors)

        super(video_PlaybackPerf, self).cleanup()
