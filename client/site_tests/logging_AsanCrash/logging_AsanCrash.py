# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import constants, cros_logging, cros_ui_test

class logging_AsanCrash(cros_ui_test.UITest):
    version = 1

    def run_once(self):
        import pyauto

        ui_log = cros_logging.LogReader(constants.UI_LOG)
        ui_log.set_start_by_current()

        logging.info('Initiate simulating memory bug to be caught by ASAN...')
        self.pyauto.SimulateAsanMemoryBug()

        # We must wait some time until memory bug is simulated (happens
        # immediately after the return on the call) and caught by ASAN.
        try:
            utils.poll_for_condition(
                lambda: ui_log.can_find('ERROR: AddressSanitizer'),
                timeout=10,
                exception=error.TestFail(
                    'Found no ui log message about Address Sanitizer catch'))

            if not ui_log.can_find("'testarray'"):
                raise error.TestFail(
                    'ASAN caught bug but did not mentioned the cause in log')

        except:
            logging.debug('UI log: ' + ui_log.get_logs())
            raise

