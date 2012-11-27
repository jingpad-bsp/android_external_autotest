# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_logging, cros_ui_test

class logging_AsanCrash(cros_ui_test.UITest):
    version = 1
    auto_login = False

    def run_once(self):
        import pyauto

        if not 'asan' in utils.read_file('/etc/session_manager_use_flags.txt'):
            raise error.TestFail('Current image not built with ASAN')

        pid = self.pyauto.GetBrowserInfo()['browser_pid']
        asan_log_name = '/var/log/chrome/asan_log.%d' % pid
        logging.info('Browser PID under pyauto control is %d. '
                     'So ASAN log is expected at %s.' % (pid, asan_log_name))

        logging.info('Initiate simulating memory bug to be caught by ASAN...')
        self.pyauto.SimulateAsanMemoryBug()

        utils.poll_for_condition(
            lambda: os.path.isfile(asan_log_name),
            timeout=10,
            exception=error.TestFail(
                    'Found no asan log file %s during 10s' % asan_log_name))
        ui_log = cros_logging.LogReader(asan_log_name)
        ui_log.read_all_logs()

        # We must wait some time until memory bug is simulated (happens
        # immediately after the return on the call) and caught by ASAN.
        try:
            utils.poll_for_condition(
                lambda: ui_log.can_find('ERROR: AddressSanitizer'),
                timeout=10,
                exception=error.TestFail(
                    'Found no asan log message about Address Sanitizer catch'))

            utils.poll_for_condition(
                lambda: ui_log.can_find("'testarray'"),
                timeout=10,
                exception=error.TestFail(
                    'ASAN caught bug but did not mentioned the cause in log'))

        except:
            logging.debug('ASAN log content: ' + ui_log.get_logs())
            raise
