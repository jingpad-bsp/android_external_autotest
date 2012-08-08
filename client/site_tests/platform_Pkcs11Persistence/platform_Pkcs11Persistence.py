# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, time

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, pkcs11

class platform_Pkcs11Persistence(cros_ui_test.UITest):
    version = 1

    def initialize(self, creds='$default'):
        super(platform_Pkcs11Persistence, self).initialize(creds)

    def run_once(self):
        if not pkcs11.wait_for_pkcs11_token():
            raise error.TestFail('The PKCS #11 token is not available.')
        result = utils.system('p11_replay --inject --replay_wifi',
                              ignore_status = True)
        if result != 0:
            raise error.TestFail('Failed to setup PKCS #11 object.')
        self.logout()
        # Work around until crosbug.com/139166 is fixed
        self.pyauto.ExecuteJavascriptInOOBEWebUI('Oobe.showSigninUI();'
            'window.domAutomationController.send("ok");')
        self.login()
        if not pkcs11.wait_for_pkcs11_token():
            raise error.TestFail('The PKCS #11 token is no longer available.')
        result = utils.system('p11_replay --replay_wifi --cleanup',
                              ignore_status = True)
        if result != 0:
            raise error.TestFail('PKCS #11 object is no longer valid.')

