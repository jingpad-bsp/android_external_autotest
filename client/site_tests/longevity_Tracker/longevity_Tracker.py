# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv
import logging
import os
import time

from autotest_lib.client.bin import site_utils
from autotest_lib.client.bin import test

TEST_DURATION = 86100  # Time (secs) of test length, 23:55 hrs.
SAMPLE_INTERVAL = 60  # Time (secs) between measurement samples.
REPORT_INTERVAL = 3600  # Time (secs) between perf data reports.
STABILIZATION_DURATION = 60  # Time for test stabilization (secs).
TMP_DIRECTORY = '/tmp/'
PERF_FILE_PREFIX = 'perf'
EXIT_FLAG_FILE = TMP_DIRECTORY + 'longevity_terminate'
OLD_FILE_AGE = 10080  # Time (mins) since file was written/modified.
CMD_REMOVE_OLD_FILES = ('find %s -name %s* -type f -mmin +%s -delete' %
                        (TMP_DIRECTORY, PERF_FILE_PREFIX, OLD_FILE_AGE))


class longevity_Tracker(test.test):
    """Monitors device stability over long periods of time."""

    version = 1

    def get_cpu_usage(self):
        """Computes percent CPU in active use for the sample interval.

        Note: This method introduces a sleep period into the test. It
        measures total CPU times at a start and end point, then computes
        percent usage between those points.

        @returns float of percent active use of CPU.

        """
        # Time between measurements is ~90% of the sample interval.
        measurement_time_delta = SAMPLE_INTERVAL * 0.90
        cpu_usage_start = site_utils.get_cpu_usage()
        time.sleep(measurement_time_delta)
        cpu_usage_end = site_utils.get_cpu_usage()
        return site_utils.compute_active_cpu_time(cpu_usage_start,
                                                  cpu_usage_end) * 100

    def get_mem_usage(self):
        """Computes percent memory in use.

        @returns float of percentage memory used of total memory.

        """
        total_memory = site_utils.get_mem_total()
        return (total_memory - site_utils.get_mem_free()) * 100 / total_memory

    def get_perf_metrics(self, cpu_values, mem_values):
        """Computes metrics for performance dashboard.

        @param cpu_values: list of sampled CPU usage values.
        @param mem_values: list of sampled Memory usage values.
        @returns metrics for CPU and Memory usage.

        """
        cpu_metric = []
        mem_metric = []
        if cpu_values and mem_values:
            cpu_metric = sorted(cpu_values)[len(cpu_values) // 2]
            mem_metric = sorted(mem_values)[len(mem_values) // 2]
        return (cpu_metric, mem_metric)

    def send_perf_metrics(self, metrics):
        """Send performance metrics to Performance Dashboard.

        @param metrics: Performance metrics for CPU and Memory usage.

        """
        logging.info('Debug: send_perf_metrics() = %s', metrics)
        # TODO(scunningham): Code to upload perf data.
        return

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

    def run_once(self):
        # Test runs 23:00 hrs, or until the exit flag file is seen.
        # Delete exit flag file at start of test.
        if os.path.isfile(EXIT_FLAG_FILE):
            os.remove(EXIT_FLAG_FILE)

        # Allow system to stabilize before start taking measurements.
        test_start_time = time.time()
        time.sleep(STABILIZATION_DURATION)

        perf_keyval = {}
        cpu_values = []
        mem_values = []
        file_name = (PERF_FILE_PREFIX +
                     time.strftime('_%Y-%m-%d_%H-%M') + '.csv')
        perf_file = open(TMP_DIRECTORY + file_name, 'w')
        writer = csv.writer(perf_file)
        writer.writerow(['time', 'cpu', 'memory'])

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
            perf_keyval['cpu_usage'] = self.get_cpu_usage()
            perf_keyval['memory_usage'] = self.get_mem_usage()
            cpu_values.append(perf_keyval['cpu_usage'])
            mem_values.append(perf_keyval['memory_usage'])
            # self.write_perf_keyval(perf_keyval)  # Need for perf dashboard?
            writer.writerow([time.strftime('%Y/%m/%d %H:%M:%S'),
                             perf_keyval['cpu_usage'],
                             perf_keyval['memory_usage']])

            # Periodically calculate and report metrics for perf dashboard.
            report_elapsed_prev_time = self.elapsed_time(report_prev_time)
            report_timer = report_elapsed_prev_time + offset
            if report_timer >= REPORT_INTERVAL:
                metrics = self.get_perf_metrics(cpu_values, mem_values)
                self.send_perf_metrics(metrics)
                writer.writerow(['Report Time = %s' %
                                 time.strftime('%Y/%m/%d %H:%M:%S'),
                                 ' CPU Usage (median) = %s' % metrics[0],
                                 ' RAM Usage (median) = %s' % metrics[1]])
                cpu_values = []
                mem_values = []

                # Set the report previous time to the current time.
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

        perf_file.close()

    def cleanup(self):
        """Delete aged perf data files and exit flag file."""
        os.system(CMD_REMOVE_OLD_FILES)
        if os.path.isfile(EXIT_FLAG_FILE):
            os.remove(EXIT_FLAG_FILE)
