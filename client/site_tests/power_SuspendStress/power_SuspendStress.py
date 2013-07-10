# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, numpy, random, time

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import power_suspend, sys_power


class power_SuspendStress(test.test):
    version = 1

    def initialize(self, duration, method='default', init_delay=0,
                   tolerated_aborts=0, breathing_time=5, min_suspend=0):
        """
        duration: total run time of the test
        method: suspend method to use... available options:
            'default': make a RequestSuspend D-Bus call to powerd
            'idle': wait for idle suspend... use with dummy_IdleSuspend
        init_delay: wait this many seconds before starting the test to give
                parallel tests time to get started
        tolerated_aborts: only fail test for SuspendAborts if they surpass
                this threshold
        breathing_time: wait this many seconds after every third suspend to
                allow Autotest/SSH to catch up
        min_suspend: suspend durations will be chosen randomly out of the
                interval between min_suspend and min_suspend + 3
        """
        self._duration = duration
        self._init_delay = init_delay
        self._tolerated_aborts = tolerated_aborts
        self._min_suspend = min_suspend
        self._breathing_time = breathing_time
        self._method = {
            'default': sys_power.do_suspend,
            'idle': sys_power.idle_suspend,
        }[method]


    def _do_suspend(self):
        self._suspender.suspend(random.randint(0, 3) + self._min_suspend)


    def run_once(self):
        time.sleep(self._init_delay)
        self._suspender = power_suspend.Suspender(
                self.resultsdir, method=self._method)
        timeout = time.time() + self._duration
        while time.time() < timeout:
            time.sleep(random.randint(0, 3))
            self._do_suspend()
            time.sleep(random.randint(0, 3))
            self._do_suspend()
            time.sleep(self._breathing_time)
            self._do_suspend()


    def postprocess_iteration(self):
        if self._suspender.successes:
            keyvals = {'suspend_iterations': len(self._suspender.successes)}
            for key in self._suspender.successes[0]:
                values = [result[key] for result in self._suspender.successes]
                keyvals[key + '_mean'] = numpy.mean(values)
                keyvals[key + '_stddev'] = numpy.std(values)
                keyvals[key + '_min'] = numpy.amin(values)
                keyvals[key + '_max'] = numpy.amax(values)
            self.write_perf_keyval(keyvals)
        if self._suspender.failures:
            total = len(self._suspender.failures)
            abort = kernel = firmware = early = 0
            for failure in self._suspender.failures:
                if type(failure) is sys_power.SuspendAbort: abort += 1
                if type(failure) is sys_power.KernelError: kernel += 1
                if type(failure) is sys_power.FirmwareError: firmware += 1
                if type(failure) is sys_power.EarlyWakeupError: early += 1
            if abort <= self._tolerated_aborts and total == abort:
                logging.warn('Ignoring %d aborted suspends (below threshold).',
                             abort)
                return
            if total == 1:
                # just throw it as is, makes aggregation on dashboards easier
                raise self._suspender.failures[0]
            raise error.TestFail('%d suspend failures in %d iterations (%d '
                    'aborts, %d kernel warnings, %d firmware errors, %d early '
                    'wakeups)' % (total, total + len(self._suspender.successes),
                    abort, kernel, firmware, early))


    def cleanup(self):
        # clean this up before we wait ages for all the log copying to finish...
        self._suspender.finalize()
