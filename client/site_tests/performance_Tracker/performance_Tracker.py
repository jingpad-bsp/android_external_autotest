# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv
import logging
import os
import time

from autotest_lib.client.bin import site_utils
from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import service_stopper

# Measurement duration [seconds] for one interation.
MEASUREMENT_DURATION = 10

TERMINATE_PATH = "/tmp/terminate"

# Time for initial test setup [seconds].
STABILIZATION_DURATION = 60

# List of thermal throttling services that should be disabled.
# - temp_metrics for link.
# - thermal for daisy, snow, pit etc.
THERMAL_SERVICES = ['temp_metrics', 'thermal']

# Time in seconds to wait for cpu idle until giveup.
WAIT_FOR_IDLE_CPU_TIMEOUT = 60.0
# Maximum percent of cpu usage considered as idle.
# Since Kiosk app runs in continuous mode, setting the idle % higher.
CPU_IDLE_USAGE = 0.7

PERF_RESULT_FILE = '/tmp/perf.csv'

class performance_Tracker(test.test):
    """Monitors cpu/memory usage."""

    version = 1

    def initialize(self):
        self._service_stopper = None
        self._original_governors = None


    def get_cpu_usage(self):
        """Computes current cpu usage in percentage.

        @returns percentage cpu used as a float.

        """
        if not utils.wait_for_idle_cpu(WAIT_FOR_IDLE_CPU_TIMEOUT,
                                       CPU_IDLE_USAGE):
            raise error.TestError('Could not get idle CPU.')
        if not utils.wait_for_cool_machine():
            raise error.TestError('Could not get cold machine.')
        cpu_usage_start = site_utils.get_cpu_usage()
        time.sleep(MEASUREMENT_DURATION)
        cpu_usage_end = site_utils.get_cpu_usage()
        return site_utils.compute_active_cpu_time(cpu_usage_start,
                                                      cpu_usage_end) * 100


    def used_mem(self):
        """Computes used memory in percentage.

        @returns percentage memory used as a float.

        """
        total_memory = site_utils.get_mem_total()
        return (total_memory - site_utils.get_mem_free()) * 100 / total_memory


    def run_once(self):
        if os.path.isfile(TERMINATE_PATH):
            os.remove(TERMINATE_PATH)

        # Stop the thermal service that may change the cpu frequency.
        self._service_stopper = service_stopper.ServiceStopper(THERMAL_SERVICES)
        self._service_stopper.stop_services()
        # Set the scaling governor to performance mode to set the cpu to the
        # highest frequency available.
        self._original_governors = utils.set_high_performance_mode()

        with chrome.Chrome() as cr:
            time.sleep(STABILIZATION_DURATION)
            perf_keyval = {}
            perf_file = open(PERF_RESULT_FILE, 'w')
            writer = csv.writer(perf_file)
            writer.writerow(['cpu', 'memory'])
            while True:
                # This test runs forever until the terminate file is created.
                if os.path.isfile(TERMINATE_PATH):
                    logging.info('Exit flag detected; exiting.')
                    perf_file.close()
                    return
                perf_keyval['cpu_usage'] = self.get_cpu_usage()
                perf_keyval['memory_usage'] = self.used_mem()
                writer.writerow([perf_keyval['cpu_usage'],
                                perf_keyval['memory_usage']])
                self.write_perf_keyval(perf_keyval)
                time.sleep(MEASUREMENT_DURATION)
            perf_file.close()


    def cleanup(self):
        # cleanup() is run by common_lib/test.py.
        if os.path.isfile(TERMINATE_PATH):
            os.remove(TERMINATE_PATH)
        if self._service_stopper:
            self._service_stopper.restore_services()
        if self._original_governors:
            utils.restore_scaling_governor_states(self._original_governors)
