# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv, logging, os
import time

from autotest_lib.client.bin import site_utils, test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import service_stopper

# Measurement duration [seconds] for one interation.
MEASUREMENT_DURATION = 10

TOTAL_TEST_DURATION = 600 # change the test time to 7 days [seconds].

# Time to exclude from calculation after launching the demo [seconds].
STABILIZATION_DURATION = 20

# List of thermal throttling services that should be disabled.
# - temp_metrics for link.
# - thermal for daisy, snow, pit etc.
THERMAL_SERVICES = ['temp_metrics', 'thermal']

# Time in seconds to wait for cpu idle until giveup.
WAIT_FOR_IDLE_CPU_TIMEOUT = 60.0
# Maximum percent of cpu usage considered as idle.
# Since Kiosk app runs in continuous mode, setting the idle % higher.
CPU_IDLE_USAGE = 0.6

_PERF_RESULT_FILE = '/tmp/perf.csv'

class enterprise_KioskPerf(test.test):
    """Enrolls to kiosk mode and monitors cpu/memory usage."""

    version = 1

    def initialize(self):
        self._service_stopper = None
        self._original_governors = None


    def test_cpu_usage(self):
        """
        Runs the video cpu usage test.

        @param local_path: the path to the video file.

        @returns a dictionary that contains the test result.
        """
        def get_cpu_usage():
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
        self._service_stopper.stop_services()
        # Set the scaling governor to performance mode to set the cpu to the
        # highest frequency available.
        self._original_governors = utils.set_high_performance_mode()
        return get_cpu_usage()


    def used_mem(self):
        """Returns total used memory in %."""
        total_memory = site_utils.get_mem_total()
        return (total_memory - site_utils.get_mem_free()) * 100 / total_memory

    def verify_enrollment(self, user_id):
        """Verifies enterprise enrollment using /home/.shadow config."""
        with open('/home/.shadow/install_attributes.pb') as f:
            if not user_id in f.read():
                raise error.TestError('Device is not enrolled or '
                                      'enterprise owned.')

    def run_once(self):
        user_id, password = utils.get_signin_credentials(os.path.join(
                os.path.dirname(os.path.realpath(__file__)), 'credentials.txt'))
        if not (user_id and password):
            logging.warn('No credentials found - exiting test.')
            return

        with chrome.Chrome(auto_login=False) as cr:
            cr.browser.oobe.NavigateEnterpriseEnrollment(user_id, password)
            time.sleep(STABILIZATION_DURATION)
            self.verify_enrollment(user_id)
            start_time = time.time()
            perf_keyval = {}
            perf_file = open(_PERF_RESULT_FILE, 'w')
            writer = csv.writer(perf_file)
            writer.writerow(['cpu','memory'])
            while (time.time() - start_time) < TOTAL_TEST_DURATION:
                perf_keyval['cpu_usage'] = self.test_cpu_usage()
                perf_keyval['memory_usage'] = self.used_mem()
                writer.writerow([perf_keyval['cpu_usage'],
                                perf_keyval['memory_usage']])
                self.write_perf_keyval(perf_keyval)
                time.sleep(10)
            perf_file.close()


    def cleanup(self):
        # cleanup() is run by common_lib/test.py.
        if self._service_stopper:
            self._service_stopper.restore_services()
        if self._original_governors:
            utils.restore_scaling_governor_states(self._original_governors)

        super(enterprise_KioskPerf, self).cleanup()
