# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
from time import sleep

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class kernel_Delay(test.test):
    """
    Test to ensure that udelay() delays at least as long as requested
    (as compared to ktime()).

    Test a variety of delays at mininmum and maximum cpu frequencies.

    """
    version = 1

    MIN_KERNEL_VER = '3.8'
    MODULE_NAME = 'udelay_test'
    UDELAY_PATH = '/sys/kernel/debug/udelay_test'
    CPUFREQ_CUR_PATH = '/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_cur_freq'
    CPUFREQ_MIN_PATH = '/sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq'
    CPUFREQ_MAX_PATH = '/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq'
    CPUFREQ_AVAIL_PATH = (
            '/sys/devices/system/cpu/cpu0/cpufreq/'
            'scaling_available_frequencies')

    # Test a variety of delays
    # 1..200, 200..500 (by 10), 500..2000 (by 100)
    DELAYS = range(1, 200) + range(200, 500, 10) + range(500, 2001, 100)
    ITERATIONS = 100

    def _set_file(self, contents, filename):
        """
        Write a string to a file.

        @param contents: the contents to write to the file
        @param filename: the filename to use

        """
        logging.debug('setting %s to %s', filename, contents)
        with open(filename, 'w') as f:
            f.write(contents)


    def _get_file(self, filename):
        """
        Read a string from a file.

        @returns: the contents of the file (string)

        """
        with open(filename, 'r') as f:
            return f.read()


    def _get_freq(self):
        """
        Get the current CPU frequency.

        @returns: the CPU frequency (int)

        """
        return int(self._get_file(self.CPUFREQ_CUR_PATH))


    def _get_min_freq(self):
        """
        Get the minimum CPU frequency.

        @returns: the CPU frequency (int)

        """
        return int(self._get_file(self.CPUFREQ_MIN_PATH))


    def _get_max_freq(self):
        """
        Get the maxium CPU frequency.

        @returns: the CPU frequency (int)

        """
        return int(self._get_file(self.CPUFREQ_MAX_PATH))


    def _unlimit_freq(self, min_freq, max_freq):
        """
        Unlimit the CPU frequency.

        @param min_freq: minimum CPU frequency available
        @param max_freq: maximum CPU frequency available

        """
        # To ensure minimum < maximum at all times, unlimit first.
        self._set_file(str(max_freq), self.CPUFREQ_MAX_PATH)
        self._set_file(str(min_freq), self.CPUFREQ_MIN_PATH)


    def _set_freq(self, freq, min_freq, max_freq):
        """
        Set the CPU frequency.

        @param freq: desired CPU frequency
        @param min_freq: minimum CPU frequency available
        @param max_freq: maximum CPU frequency available

        """
        # To ensure minimum < maximum at all times, unlimit first.
        self._unlimit_freq(min_freq, max_freq)
        # Wait a moment for new scaling to take effect before setting.
        sleep(0.2)
        self._set_file(str(freq), self.CPUFREQ_MAX_PATH)
        self._set_file(str(freq), self.CPUFREQ_MIN_PATH)

        # Sometimes the frequency doesn't set right away, give it some time.
        for x in range(0, 10):
            cur_freq = self._get_freq()
            logging.info('cpu freq set to %d', cur_freq)
            if cur_freq == freq:
                return
            sleep(0.1)

        raise error.TestFail('unable to set freq to %d' % freq)


    def _test_udelay(self, usecs):
        """
        Test udelay() for a given amount of time.

        @param usecs: number of usecs to delay for each iteration

        """
        self._set_file('%d %d' % (usecs, self.ITERATIONS), self.UDELAY_PATH)
        with open(self.UDELAY_PATH, 'r') as f:
            for line in f:
                line = line.rstrip()
                logging.info('result: %s', line)
                if 'FAIL' in line:
                    raise error.TestFail('udelay failed: %s' % line)


    def run_once(self):
        kernel_ver = os.uname()[2]
        if utils.compare_versions(kernel_ver, self.MIN_KERNEL_VER) < 0:
            logging.info(
                    'skipping test: old kernel %s (min %s) missing module %s',
                    kernel_ver, self.MIN_KERNEL_VER, self.MODULE_NAME)
            return

        utils.load_module(self.MODULE_NAME)

        with open(self.CPUFREQ_AVAIL_PATH, 'r') as f:
            available_freqs = [int(x) for x in f.readline().split()]

        max_freq = max(available_freqs)
        min_freq = min(available_freqs)
        logging.info('cpu frequency max %d min %d', max_freq, min_freq)

        freqs = [ min_freq, max_freq ]
        for freq in freqs:
            self._set_freq(freq, min_freq, max_freq)
            for usecs in self.DELAYS:
                self._test_udelay(usecs)
            if freq != self._get_min_freq() or freq != self._get_max_freq():
                raise error.TestFail(
                        'cpu frequency changed from %d to %d-%d' % (
                        freq, self._get_min_freq(), self._get_max_freq()))

        self._unlimit_freq(min_freq, max_freq)
        utils.unload_module(self.MODULE_NAME)
