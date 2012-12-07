# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class graphics_LibDRM(test.test):
    version = 1

    def run_once(self):
        num_errors = 0
        keyvals = {}

        # These are tests to run for all platforms.
        tests_common = ['modetest']

        # Determine which tests to run based on the architecture type.
        tests_intel = ['gem_basic', 'gem_flink', 'gem_mmap', 'gem_readwrite']
        arch_tests = { 'arm'   : [],
                       'i386'  : tests_intel,
                       'x86_64': tests_intel }
        arch = utils.get_cpu_arch()
        if not arch in arch_tests:
            raise error.TestFail('Architecture "%s" not supported.' % arch)
        tests = tests_common + arch_tests[arch]

        for test in tests:
            # Make sure the test exists on this system.  Not all tests may be
            # present on a given system.
            if utils.system('which %s' % test):
                logging.error('Could not find test %s.' % test)
                keyvals[test] = 'NOT FOUND'
                num_errors += 1
                continue

            # Run the test and check for success based on return value.
            return_value = utils.system(test)
            if utils.system(test):
                logging.error('%s returned %d' % (test, return_value))
                num_errors += 1
                keyvals[test] = 'FAILED'
            else:
                keyvals[test] = 'PASSED'

        self.write_perf_keyval(keyvals)

        if num_errors > 0:
            raise error.TestError('One or more libdrm tests failed.')
