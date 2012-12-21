# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, numpy, os, random, time

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import power_suspend, sys_power


class power_SuspendStress(test.test):
    version = 1

    def initialize(self, duration, use_dbus=False, init_delay=0):
        # Only use use_dbus in parallel with another test that does a login
        self._duration = duration
        self._use_dbus = use_dbus
        self._init_delay = init_delay


    def run_once(self):
        time.sleep(self._init_delay)
        self._suspender = power_suspend.Suspender(use_dbus=self._use_dbus)
        timeout = time.time() + self._duration
        while time.time() < timeout:
            # TODO: tweak both values, make them board and payload dependent
            time.sleep(random.randint(0, 15))
            self._suspender.suspend(random.randint(10, 15))


    def postprocess_iteration(self):
        keyvals = {'suspend_iterations': len(self._suspender.successes)}
        for key in self._suspender.successes[0]:
            values = [result[key] for result in self._suspender.successes]
            keyvals[key + '_mean'] = numpy.mean(values)
            keyvals[key + '_stddev'] = numpy.std(values)
            keyvals[key + '_min'] = numpy.amin(values)
            keyvals[key + '_max'] = numpy.amax(values)
        self.write_perf_keyval(keyvals)
        if self._suspender.failures:
            abort = kernel = firmware = early = 0
            total = len(self._suspender.failures)
            for failure in self._suspender.failures:
                if type(failure) is sys_power.SuspendAbort: abort += 1
                if type(failure) is sys_power.KernelError: kernel += 1
                if type(failure) is sys_power.FirmwareError: firmware += 1
                if type(failure) is sys_power.EarlyWakeupError: early += 1
            raise error.TestFail('%d suspend failures in %d iterations (%d '
                    'aborts, %d kernel warnings, %d firmware errors, %d early '
                    'wakeups)' % (total, total + len(self._suspender.successes),
                    abort, kernel, firmware, early))
