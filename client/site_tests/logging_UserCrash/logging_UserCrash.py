# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, subprocess
from signal import SIGSEGV
from autotest_lib.client.bin import site_log_reader, test
from autotest_lib.client.common_lib import error, utils

_CRASH_PATH = '/sbin/crash_reporter'
_CORE_PATTERN = '/proc/sys/kernel/core_pattern'

class logging_UserCrash(test.test):
    version = 1


    def setup(self):
        os.chdir(self.srcdir)
        utils.system('make clean all')


    def run_once(self):
        # autotest has modified core_pattern, so we need to
        # make sure crash_reporter resets it.
        utils.system('%s --init --nounclean_check' % _CRASH_PATH)
        output = utils.read_file(_CORE_PATTERN).rstrip()
        expected_core_pattern = ('|%s --signal=%%s --pid=%%p --exec=%%e' %
                                 _CRASH_PATH)
        if output != expected_core_pattern:
            raise error.TestFail('core pattern should have been %s, not %s' %
                                 (expected_core_pattern, output))

        log_reader = site_log_reader.LogReader()
        log_reader.set_start_by_reboot(-1)

        if not log_reader.can_find('Enabling crash handling'):
            raise error.TestFail(
                'user space crash handling was not started during last boot')

        log_reader.set_start_by_current()
        crasher = subprocess.Popen(os.path.join(self.srcdir, 'crasher'))
        if crasher.wait() != -SIGSEGV:
            raise error.TestFail('crasher did not do its job of crashing')

        expected_message = ('Received crash notification for '
                            'crasher[%d] sig 11' % crasher.pid)
        if not log_reader.can_find(expected_message):
            raise error.TestFail('Did not find segv message: %s' %
                                 expected_message)

        log_reader.set_start_by_current()
        utils.system('%s --clean_shutdown' % _CRASH_PATH)
        output = utils.read_file(_CORE_PATTERN).rstrip()
        if output != 'core':
            raise error.TestFail('core pattern should have been core, not %s' %
                                 output)
