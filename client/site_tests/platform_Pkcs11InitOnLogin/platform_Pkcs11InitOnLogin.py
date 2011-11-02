# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, time

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import constants, cros_ui_test, pkcs11

class TimeoutError(error.TestError):
    pass


class platform_Pkcs11InitOnLogin(cros_ui_test.UITest):
    version = 1

    def initialize(self, creds='$default', **dargs):
        self.auto_login = False
        super(platform_Pkcs11InitOnLogin, self).initialize(
            creds, is_creating_owner=True, **dargs)
        self.login(self.username, self.password)


    def run_once(self):
        # Make sure we start from a fresh state.
        if os.access(constants.PKCS11_INIT_MAGIC_FILE, os.F_OK):
            raise error.TestFail('PKCS#11 already initialized!')
        start_time = time.time()
        # Wait for PKCS#11 initialization to complete.
        try:
            utils.poll_for_condition(
                lambda: os.access(constants.PKCS11_INIT_MAGIC_FILE, os.F_OK),
                TimeoutError('Timed out waiting for PKCS#11 initialization!'),
                timeout=60)
            end_time = time.time()
            self.write_perf_keyval(
                { 'seconds_pkcs11_onlogin_init': end_time - start_time } )
            if not pkcs11.verify_pkcs11_initialized():
              raise error.TestFail('Initialized token failed checks!')
        except TimeoutError, e:
            logging.error(e)
