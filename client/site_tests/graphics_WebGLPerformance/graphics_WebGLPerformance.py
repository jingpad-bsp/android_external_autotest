# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a client side WebGL performance test."""

import logging, os, time

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome


class graphics_WebGLPerformance(test.test):
    """WebGL performance graphics test."""
    version = 1

    def setup(self):
        self.job.setup_dep(['webgl_perf'])
        self.job.setup_dep(['graphics'])

    def initialize(self):
        self.perf_keyval = {}

    def poll_for_condition(self, tab, condition, error_msg):
        """Waits until javascript condition is true.

        @param tab:       The tab the javascript/condition runs on.
        @param condition: The javascript condition to evaluate.
        @param error_msg: Test failure error string on timeout.
        """
        utils.poll_for_condition(
            lambda: tab.EvaluateJavaScript(condition),
            exception=error.TestError(error_msg),
            timeout=self.test_duration_secs,
            sleep_interval=1)

    def run_performance_test(self, browser, test_url):
        """Runs the performance test from the given url.

        @param browser: The Browser object to run the test with.
        @param test_url: The URL to the performance test site.
        """
        # Wait 5 seconds for the system to stabilize.
        # TODO(ihf): Add a function that waits for low system load.
        time.sleep(5)

        # Kick off test.
        tab = browser.tabs.New()
        tab.Navigate(test_url)
        tab.Activate()

        # Wait for test completion.
        self.poll_for_condition(tab, 'time_ms_geom_mean > 0.0',
            'Timed out running the test.')

        # Get the geometric mean of individual runtimes.
        time_ms_geom_mean = tab.EvaluateJavaScript(
                               'time_ms_geom_mean')
        logging.info('WebGLPerformance: time_ms_geom_mean = %f',
                                      time_ms_geom_mean)

        # Output numbers for plotting by harness.
        keyvals = {}
        keyvals['time_ms_geom_mean'] = time_ms_geom_mean
        self.write_perf_keyval(keyvals)
        self.output_perf_value(description='time_geom_mean',
                               value=time_ms_geom_mean, units='ms',
                               higher_is_better=False,
                               graph='time_geom_mean')
        # Add extra value to the graph distinguishing different boards.
        variant = utils.get_board_with_frequency_and_memory()
        desc = 'time_geom_mean (%s)' % variant
        self.output_perf_value(description=desc,
                               value=time_ms_geom_mean, units='ms',
                               higher_is_better=False,
                               graph='time_geom_mean')

        # Get a copy of the test report.
        test_report = tab.EvaluateJavaScript('test_report')
        results_path = os.path.join(self.bindir,
            "../../results/default/graphics_WebGLPerformance/test_report.html")
        f = open(results_path, 'w+')
        f.write(test_report)
        f.close()

        tab.Close()

    def run_once(self, test_duration_secs=600, fullscreen=True):
        """Finds a brower with telemetry, and run the test.

        @param test_duration_secs: The test duration in seconds.
        @param fullscreen: Whether to run the test in fullscreen.
        """
        self.test_duration_secs = test_duration_secs

        ext_paths = []
        if fullscreen:
            ext_paths.append(
                    os.path.join(self.autodir, 'deps', 'graphics',
                                 'graphics_test_extension'))

        with chrome.Chrome(logged_in=False, extension_paths=ext_paths) as cr:
            websrc_dir = os.path.join(self.autodir, 'deps', 'webgl_perf', 'src')
            if not cr.browser.SetHTTPServerDirectories(websrc_dir):
                raise error.TestError('Unable to start HTTP server')
            test_url = cr.browser.http_server.UrlOf(
                    os.path.join(websrc_dir, 'webgl-performance-tests.html'))
            self.run_performance_test(cr.browser, test_url)

