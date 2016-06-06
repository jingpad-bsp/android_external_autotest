# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv
import glob
import httplib
import json
import logging
import os
import re
import shutil
import time
import urllib
import urllib2

from autotest_lib.client.bin import site_utils
from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.cros import constants

TEST_DURATION = 72000  # Duration of test (20 hrs) in seconds.
SAMPLE_INTERVAL = 60  # Length of measurement samples in seconds.
REPORT_INTERVAL = 3600  # Interval between perf data reports in seconds.
STABILIZATION_DURATION = 60  # Time for test stabilization in seconds.
TMP_DIRECTORY = '/tmp/'
PERF_FILE_NAME_PREFIX = 'perf'
EXIT_FLAG_FILE = TMP_DIRECTORY + 'longevity_terminate'
OLD_FILE_AGE = 14400  # Age of old files to be deleted in minutes = 10 days.
# The manifest.json file for a Chrome extension contains the app name, id,
# version, and other info for the app. It is accessible by the OS only when
# the app is running and it's cryptohome directory mounted. Only one Kiosk app
# can be running at a time.
MANIFEST_PATTERN = '/home/.shadow/*/mount/user/Extensions/*/*/manifest.json'
VERSION_PATTERN = r'^(\d+)\.(\d+)\.(\d+)\.(\d+)$'
DASHBOARD_UPLOAD_URL = 'https://chromeperf.appspot.com/add_point'


class PerfUploadingError(Exception):
    """Exception raised in perf_uploader."""
    pass


class longevity_Tracker(test.test):
    """Monitor device and App stability over long periods of time."""

    version = 1

    def initialize(self):
        self.temp_dir = os.path.split(self.tmpdir)[0]

    def _get_cpu_usage(self):
        """Compute percent CPU in active use for the sample interval.

        Note: This method introduces a sleep period into the test, equal to
        90% of the sample interval.

        @returns float of percent active use of CPU.

        """
        # Time between measurements is ~90% of the sample interval.
        measurement_time_delta = SAMPLE_INTERVAL * 0.90
        cpu_usage_start = site_utils.get_cpu_usage()
        time.sleep(measurement_time_delta)
        cpu_usage_end = site_utils.get_cpu_usage()
        return site_utils.compute_active_cpu_time(cpu_usage_start,
                                                  cpu_usage_end) * 100

    def _get_mem_usage(self):
        """Compute percent memory in active use.

        @returns float of percent memory in use.

        """
        total_memory = site_utils.get_mem_total()
        free_memory = site_utils.get_mem_free()
        return ((total_memory - free_memory) / total_memory) * 100

    def _get_max_temperature(self):
        """Get temperature of hottest sensor in Celsius.

        @returns float of temperature of hottest sensor.

        """
        temperature = utils.get_current_temperature_max()
        if not temperature:
            temperature = 0
        return temperature

    def _get_hwid(self):
        """Get hwid of test device, e.g., 'WOLF C4A-B2B-A47'.

        @returns string of hwid (Hardware ID) of device under test.

        """
        with os.popen('crossystem hwid 2>/dev/null', 'r') as hwid_proc:
            hwid = hwid_proc.read()
        if not hwid:
            hwid = 'undefined'
        return hwid

    def elapsed_time(self, mark_time):
        """Get time elapsed since |mark_time|.

        @param mark_time: point in time from which elapsed time is measured.
        @returns time elapsed since the marked time.

        """
        return time.time() - mark_time

    def modulo_time(self, timer, interval):
        """Get time eplased on |timer| for the |interval| modulus.

        Value returned is used to adjust the timer so that it is synchronized
        with the current interval.

        @param timer: time on timer, in seconds.
        @param interval: period of time in seconds.
        @returns time elapsed from the start of the current interval.

        """
        return timer % int(interval)

    def syncup_time(self, timer, interval):
        """Get time remaining on |timer| for the |interval| modulus.

        Value returned is used to induce sleep just long enough to put the
        process back in sync with the timer.

        @param timer: time on timer, in seconds.
        @param interval: period of time in seconds.
        @returns time remaining till the end of the current interval.

        """
        return interval - (timer % int(interval))

    def _record_perf_values(self, perf_values, perf_writer):
        """Records performance values.

        @param perf_values: dict measures of performance values.
        @param perf_writer: file for writing performance values.

        """
        cpu_usage = '%.3f' % self._get_cpu_usage()
        mem_usage = '%.3f' % self._get_mem_usage()
        max_temp = '%.3f' % self._get_max_temperature()
        time_stamp = time.strftime('%Y/%m/%d %H:%M:%S')
        perf_writer.writerow([time_stamp, cpu_usage, mem_usage, max_temp])
        logging.info('Time: %s, CPU: %s, Mem: %s, Temp: %s',
                     time_stamp, cpu_usage, mem_usage, max_temp)
        perf_values['cpu'].append(cpu_usage)
        perf_values['mem'].append(mem_usage)
        perf_values['temp'].append(max_temp)

    def _record_90th_metrics(self, perf_values, perf_metrics):
        """Records 90th percentile metric of attribute performance values.

        @param perf_values: dict attribute performance values.
        @param perf_metrics: dict attribute 90%-ile performance metrics.

        """
        # Calculate 90th percentile for each attribute.
        cpu_values = perf_values['cpu']
        mem_values = perf_values['mem']
        temp_values = perf_values['temp']
        cpu_metric = sorted(cpu_values)[(len(cpu_values) * 9) // 10]
        mem_metric = sorted(mem_values)[(len(mem_values) * 9) // 10]
        temp_metric = sorted(temp_values)[(len(temp_values) * 9) // 10]
        logging.info('== Performance values: %s', perf_values)
        logging.info('== 90th percentile: cpu: %s, mem: %s, temp: %s',
                     cpu_metric, mem_metric, temp_metric)

        # Append 90th percentile to each attribute performance metric.
        perf_metrics['cpu'].append(cpu_metric)
        perf_metrics['mem'].append(mem_metric)
        perf_metrics['temp'].append(temp_metric)

    def _get_median_metrics(self, metrics):
        """Returns median of each attribute performance metric.

        If no metric values were recorded, return 0 for each metric.

        @param metrics: dict of attribute performance metric lists.
        @returns dict of attribute performance metric medians.

        """
        if len(metrics['cpu']):
            cpu_metric = sorted(metrics['cpu'])[len(metrics['cpu']) // 2]
            mem_metric = sorted(metrics['mem'])[len(metrics['mem']) // 2]
            temp_metric = sorted(metrics['temp'])[len(metrics['temp']) // 2]
        else:
            cpu_metric = 0
            mem_metric = 0
            temp_metric = 0
        logging.info('== Median: cpu: %s, mem: %s, temp: %s',
                     cpu_metric, mem_metric, temp_metric)
        return {'cpu': cpu_metric, 'mem': mem_metric, 'temp': temp_metric}

    def _copy_perf_file_to_results_directory(self, perf_file):
        """Copy performance file to perf.csv file for AutoTest results.

        Note: The AutoTest results default directory is located at /usr/local/
        autotest/results/default/longevity_Tracker/results

        @param perf_file: Performance results file path.

        """
        results_file = os.path.join(self.resultsdir, 'perf.csv')
        shutil.copy(perf_file, results_file)
        logging.info('Copied %s to %s)', perf_file, results_file)

    def _write_perf_keyvals(self, perf_results):
        """Write perf results to keyval file for AutoTest results.

        @param perf_metrics: dict of attribute performance metrics.

        """
        perf_keyval = {}
        perf_keyval['cpu_usage'] = perf_results['cpu']
        perf_keyval['memory_usage'] = perf_results['mem']
        perf_keyval['temperature'] = perf_results['temp']
        self.write_perf_keyval(perf_keyval)

    def _write_perf_results(self, perf_results):
        """Write perf results to results-chart.json file for Perf Dashboard.

        @param perf_metrics: dict of attribute performance metrics.

        """
        cpu_metric = perf_results['cpu']
        mem_metric = perf_results['mem']
        ec_metric = perf_results['temp']
        self.output_perf_value(description='cpu_usage', value=cpu_metric,
                               units='%', higher_is_better=False)
        self.output_perf_value(description='mem_usage', value=mem_metric,
                               units='%', higher_is_better=False)
        self.output_perf_value(description='max_temp', value=ec_metric,
                               units='Celsius', higher_is_better=False)

    def _read_perf_results(self):
        results_file = os.path.join(self.resultsdir, 'results-chart.json')
        with open(results_file, 'r') as fp:
            contents = fp.read()
            chart_data = json.loads(contents)
        return chart_data

    def _get_id_from_version(self, chrome_version, cros_version):
        """Compute the point ID from Chrome and ChromeOS version numbers.

        @param chrome_ver: The Chrome version number as a string.
        @param cros_version: The ChromeOS version number as a string.

        @return unique integer ID associated with the given version numbers.

        """
        # Number of digits from each part of the Chrome and Chrome OS version
        # strings to use when building the point ID.
        chrome_version_col_widths = [0, 0, 5, 3]
        cros_version_col_widths = [0, 5, 3, 2]

        def get_digits_from_version(version_num, column_widths):
            if re.match(VERSION_PATTERN, version_num):
                computed_string = ''
                version_parts = version_num.split('.')
                for i, version_part in enumerate(version_parts):
                    if column_widths[i]:
                        computed_string += version_part.zfill(column_widths[i])
                return computed_string
            else:
                return None
        chrome_digits = get_digits_from_version(chrome_version,
                                                chrome_version_col_widths)
        cros_digits = get_digits_from_version(cros_version,
                                              cros_version_col_widths)
        if not chrome_digits or not cros_digits:
            return None
        result_digits = chrome_digits + cros_digits
        max_digits = sum(chrome_version_col_widths + cros_version_col_widths)
        if len(result_digits) > max_digits:
            return None
        return int(result_digits)

    def _get_kiosk_app_info(self):
        """Get kiosk app name and version from manifest.json file.

        Get the kiosk name and version strings from the manifest of the
        Extension in the currently running session. Return 'none' if no
        manifest is found, 'unknown' if multiple manifests are found, or
        'undefined' if single manifest is found, but does not specify the
        name or version.

        @returns dict of Kiosk name and version number strings.

        """
        kiosk_info = {}
        file_paths = glob.glob(MANIFEST_PATTERN)
        # If current session has no Extensions, set 'none'.
        if len(file_paths) == 0:
            return {'name': 'none', 'version': 'none'}
        # If current session has multiple Extensions, then set 'unknown'.
        if len(file_paths) > 1:
            return {'name': 'unknown', 'version': 'unknown'}
        kiosk_manifest = open(file_paths[0], 'r').read()
        manifest_json = json.loads(kiosk_manifest)
        # If manifest is missing name or version, then set 'undefined'.
        kiosk_info['name'] = manifest_json.get('name', 'undefined')
        kiosk_info['version'] = manifest_json.get('version', 'undefined')
        return kiosk_info

    def _format_data_for_upload(self, chart_data):
        """Collect chart data into an uploadable data JSON object.

        @param chart_data: performance results formatted as chart data.

        """
        perf_values = {
            'format_version': '1.0',
            'benchmark_name': self.test_suite_name,
            'charts': chart_data,
        }

        dash_entry = {
            'master': 'ChromeOS_Enterprise',
            'bot': 'cros-%s' % self.board_name,
            'point_id': self.point_id,
            'versions': {
                'cros_version': self.chromeos_version,
                'chrome_version': self.chrome_version,
            },
            'supplemental': {
                'default_rev': 'r_cros_version',
                'hardware_identifier': 'a_' + self.hw_id,
                'kiosk_app_name': 'a_' + self.kiosk_app_name,
                'kiosk_app_version': 'r_' + self.kiosk_app_version
            },
            'chart_data': perf_values
        }
        return {'data': json.dumps(dash_entry)}

    def _send_to_dashboard(self, data_obj):
        """Send formatted perf data to the perf dashboard.

        @param data_obj: data object as returned by _format_data_for_upload().

        @raises PerfUploadingError if an exception was raised when uploading.

        """
        encoded = urllib.urlencode(data_obj)
        req = urllib2.Request(DASHBOARD_UPLOAD_URL, encoded)
        try:
            urllib2.urlopen(req)
        except urllib2.HTTPError as e:
            raise PerfUploadingError('HTTPError: %d %s for JSON %s\n' %
                                     (e.code, e.msg, data_obj['data']))
        except urllib2.URLError as e:
            raise PerfUploadingError('URLError: %s for JSON %s\n' %
                                     (str(e.reason), data_obj['data']))
        except httplib.HTTPException:
            raise PerfUploadingError('HTTPException for JSON %s\n' %
                                     data_obj['data'])

    def _get_chrome_version(self):
        """Get the Chrome version number and milestone as strings.

        Invoke "chrome --version" to get the version number and milestone.

        @return A tuple (chrome_ver, milestone) where "chrome_ver" is the
            current Chrome version number as a string (in the form "W.X.Y.Z")
            and "milestone" is the first component of the version number
            (the "W" from "W.X.Y.Z").  If the version number cannot be parsed
            in the "W.X.Y.Z" format, the "chrome_ver" will be the full output
            of "chrome --version" and the milestone will be the empty string.

        """
        chrome_version = utils.system_output(constants.CHROME_VERSION_COMMAND,
                                             ignore_status=True)
        chrome_version = utils.parse_chrome_version(chrome_version)
        return chrome_version

    def _run_test_cycle(self):
        """Run long-duration test cycle and collect performance metrics.

        @returns list of median performance metrics.

        """
        # Allow system to stabilize before start taking measurements.
        test_start_time = time.time()
        time.sleep(STABILIZATION_DURATION)

        perf_values = {'cpu': [], 'mem': [], 'temp': []}
        perf_metrics = {'cpu': [], 'mem': [], 'temp': []}
        perf_file_name = (PERF_FILE_NAME_PREFIX +
                          time.strftime('_%Y-%m-%d_%H-%M') + '.csv')
        perf_file_path = os.path.join(self.temp_dir, perf_file_name)
        perf_file = open(perf_file_path, 'w')
        perf_writer = csv.writer(perf_file)
        perf_writer.writerow(['Time', 'CPU', 'Memory', 'Temperature (C)'])

        # Align time of loop start with the sample interval.
        test_elapsed_time = self.elapsed_time(test_start_time)
        time.sleep(self.syncup_time(test_elapsed_time, SAMPLE_INTERVAL))
        test_elapsed_time = self.elapsed_time(test_start_time)

        report_start_time = time.time()
        report_prev_time = report_start_time

        report_elapsed_prev_time = self.elapsed_time(report_prev_time)
        offset = self.modulo_time(report_elapsed_prev_time, REPORT_INTERVAL)
        report_timer = report_elapsed_prev_time + offset
        while self.elapsed_time(test_start_time) <= TEST_DURATION:
            if os.path.isfile(EXIT_FLAG_FILE):
                logging.info('Exit flag file detected. Exiting test.')
                break
            self._record_perf_values(perf_values, perf_writer)

            # Periodically calculate and record 90th percentile metrics.
            report_elapsed_prev_time = self.elapsed_time(report_prev_time)
            report_timer = report_elapsed_prev_time + offset
            if report_timer >= REPORT_INTERVAL:
                self._record_90th_metrics(perf_values, perf_metrics)
                perf_values = {'cpu': [], 'mem': [], 'temp': []}

                # Set report previous time to current time.
                report_prev_time = time.time()
                report_elapsed_prev_time = self.elapsed_time(report_prev_time)

                # Calculate offset based on the original report start time.
                report_elapsed_time = self.elapsed_time(report_start_time)
                offset = self.modulo_time(report_elapsed_time, REPORT_INTERVAL)

                # Set the timer to time elapsed plus offset to next interval.
                report_timer = report_elapsed_prev_time + offset

            # Sync the loop time to the sample interval.
            test_elapsed_time = self.elapsed_time(test_start_time)
            time.sleep(self.syncup_time(test_elapsed_time, SAMPLE_INTERVAL))

        # Close perf file and copy to results directory.
        perf_file.close()
        self._copy_perf_file_to_results_directory(perf_file_path)

        # Return median of each attribute performance metric.
        return self._get_median_metrics(perf_metrics)

    def run_once(self, subtest_name=None):
        self.board_name = utils.get_board()
        self.hw_id = self._get_hwid()
        self.chrome_version = self._get_chrome_version()[0]
        self.chromeos_version = '0.' + utils.get_chromeos_release_version()
        self.point_id = self._get_id_from_version(self.chrome_version,
                                                  self.chromeos_version)
        kiosk_info = self._get_kiosk_app_info()
        self.kiosk_app_name = kiosk_info['name']
        self.kiosk_app_version = kiosk_info['version']
        self.test_suite_name = self.tagged_testname
        if subtest_name:
            self.test_suite_name += '.' + subtest_name

        # Delete exit flag file at start of test run.
        if os.path.isfile(EXIT_FLAG_FILE):
            os.remove(EXIT_FLAG_FILE)

        # Run a single test cycle.
        self.perf_results = {'cpu': '0', 'mem': '0', 'temp': '0'}
        self.perf_results = self._run_test_cycle()

        # Write results for AutoTest to pick up at end of test.
        self._write_perf_keyvals(self.perf_results)
        self._write_perf_results(self.perf_results)

        # Post perf results directly to performance dashboard iff the test is
        # not being run from an AutoTest job (i.e., job.serverdir is None).
        # View uploaded data at https://chromeperf.appspot.com/new_points,
        # with test path pattern=ChromeOS_Enterprise/cros-*/longevity*/*
        if not self.job.serverdir:
            chart_data = self._read_perf_results()
            data_obj = self._format_data_for_upload(chart_data)
            self._send_to_dashboard(data_obj)

    def cleanup(self):
        """Delete aged perf data files and the exit flag file."""
        cmd = ('find %s -name %s* -type f -mmin +%s -delete' %
               (self.temp_dir, PERF_FILE_NAME_PREFIX, OLD_FILE_AGE))
        os.system(cmd)
        if os.path.isfile(EXIT_FLAG_FILE):
            os.remove(EXIT_FLAG_FILE)
