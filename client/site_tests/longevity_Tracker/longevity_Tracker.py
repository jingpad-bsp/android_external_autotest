# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv, logging, os, shutil, time

from autotest_lib.client.bin import site_utils, test, utils

TEST_DURATION = 82800  # Duration of test (23 hrs) in seconds.
SAMPLE_INTERVAL = 60  # Length of measurement samples in seconds.
REPORT_INTERVAL = 3600  # Interval between perf data reports in seconds.
STABILIZATION_DURATION = 60  # Time for test stabilization in seconds.
TMP_DIRECTORY = '/tmp/'
PERF_FILE_NAME_PREFIX = 'perf'
EXIT_FLAG_FILE = TMP_DIRECTORY + 'longevity_terminate'
OLD_FILE_AGE = 14400  # Age of old files to be deleted in minutes = 10 days.


class longevity_Tracker(test.test):
    """Monitors device and App stability over long periods of time."""

    version = 1

    def initialize(self):
        self.temp_dir = os.path.split(self.tmpdir)[0]

    def _get_cpu_usage(self):
        """Computes percent CPU in active use for the sample interval.

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
        """Computes percent memory in active use.

        @returns float of percent memory in use.

        """
        total_memory = site_utils.get_mem_total()
        free_memory = site_utils.get_mem_free()
        return ((total_memory - free_memory) / total_memory) * 100

    def _get_max_temperature(self):
        """Gets temperature of hottest sensor in Celsius.

        @returns float of temperature of hottest sensor.

        """
        temperature = utils.get_current_temperature_max()
        if not temperature:
            temperature = 0
        return temperature

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

    def _write_perf_keyvals(self, perf_metrics):
        """Write perf metrics to keyval file for AutoTest results.

        @param perf_metrics: dict of attribute performance metrics.

        """
        perf_keyval = {}
        perf_keyval['cpu_usage'] = perf_metrics['cpu']
        perf_keyval['memory_usage'] = perf_metrics['mem']
        perf_keyval['temperature'] = perf_metrics['temp']
        self.write_perf_keyval(perf_keyval)

    def _write_perf_results(self, perf_metrics):
        """Write perf metrics to results-chart file for Performance Dashboard.

        @param perf_metrics: dict of attribute performance metrics.

        """
        cpu_metric = perf_metrics['cpu']
        mem_metric = perf_metrics['mem']
        ec_metric = perf_metrics['temp']
        self.output_perf_value(description='cpu_usage', value=cpu_metric,
                               units='%', higher_is_better=False)
        self.output_perf_value(description='mem_usage', value=mem_metric,
                               units='%', higher_is_better=False)
        self.output_perf_value(description='max_temp', value=ec_metric,
                               units='Celsius', higher_is_better=False)

    def _run_test_cycle(self):
        """Run 23-hour test cycle and collect performance metrics.

        @returns list of median performance metrics.

        """
        # Allow system to stabilize before start taking measurements.
        test_start_time = time.time()
        time.sleep(STABILIZATION_DURATION)

        board_name = utils.get_current_board()
        build_id = utils.get_chromeos_release_version()
        perf_values = {'cpu': [], 'mem': [], 'temp': []}
        perf_metrics = {'cpu': [], 'mem': [], 'temp': []}
        perf_file_name = (PERF_FILE_NAME_PREFIX +
                          time.strftime('_%Y-%m-%d_%H-%M') + '.csv')
        perf_file_path = os.path.join(self.temp_dir, perf_file_name)
        perf_file = open(perf_file_path, 'w')
        perf_writer = csv.writer(perf_file)
        perf_writer.writerow(['Time', 'CPU', 'Memory', 'Temperature (C)'])
        logging.info('Board Name: %s, Build ID: %s', board_name, build_id)

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

    def run_once(self):
        # Delete exit flag file at start of test run.
        if os.path.isfile(EXIT_FLAG_FILE):
            os.remove(EXIT_FLAG_FILE)

        # Run a single 23-hour test cycle.
        median_metrics = {'cpu': '0', 'mem': '0', 'temp': '0'}
        median_metrics = self._run_test_cycle()

        # Write metrics to keyval file for AutoTest results.
        self._write_perf_keyvals(median_metrics)

        # Write metrics to results-chart.json file for performance dashboard.
        self._write_perf_results(median_metrics)

    def cleanup(self):
        """Delete aged perf data files and the exit flag file."""
        cmd = ('find %s -name %s* -type f -mmin +%s -delete' %
               (self.temp_dir, PERF_FILE_NAME_PREFIX, OLD_FILE_AGE))
        os.system(cmd)
        if os.path.isfile(EXIT_FLAG_FILE):
            os.remove(EXIT_FLAG_FILE)
