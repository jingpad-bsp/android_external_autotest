# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, time
from autotest_lib.client.bin import site_log_reader, site_ui_test, test
from autotest_lib.client.common_lib import error, utils

_CRASH_PATH = '/sbin/crash_reporter'
_PENDING_SHUTDOWN_PATH = '/var/lib/crash_reporter/pending_clean_shutdown'
_UNCLEAN_SHUTDOWN_MESSAGE = 'Last shutdown was not clean'

class logging_KernelCrash(site_ui_test.UITest):
    version = 1
    auto_login = False


    def run_once(self):
        if not os.path.exists(_PENDING_SHUTDOWN_PATH):
            raise error.TestFail('pending shutdown file, %s, not found' %
                                 _PENDING_SHUTDOWN_PATH)

        log_reader = site_log_reader.LogReader()
        log_reader.set_start_by_reboot(-1)

        if log_reader.can_find(_UNCLEAN_SHUTDOWN_MESSAGE):
            raise error.TestFail(
                'Unexpectedly detected kernel crash during boot')

	# Log in and out twice to make sure that doesn't cause
	# an unclean shutdown message.
	for i in range(2):
	  self.login()
	  time.sleep(5)
	  self.logout()
	  time.sleep(5)

        if log_reader.can_find(_UNCLEAN_SHUTDOWN_MESSAGE):
            logging.info('Unexpected logs: ', log_reader.get_logs())
            raise error.TestFail(
                'Unexpectedly detected kernel crash during login/logout')

        # Run the shutdown and verify it does not complain of unclean
        # shutdown.

        log_reader.set_start_by_current()
        utils.system('%s --clean_shutdown' % _CRASH_PATH)
        utils.system('%s --init' % _CRASH_PATH)

        if log_reader.can_find(_UNCLEAN_SHUTDOWN_MESSAGE):
            raise error.TestFail('Incorrectly signalled unclean shutdown')

        # Now simulate an unclean shutdown and test handling.

        log_reader.set_start_by_current()
        utils.system('%s --init' % _CRASH_PATH)

        if not log_reader.can_find(_UNCLEAN_SHUTDOWN_MESSAGE):
            raise error.TestFail('Did not signal unclean shutdown when should')
