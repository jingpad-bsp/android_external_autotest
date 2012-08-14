# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib, logging, os, time, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import constants, cros_logging, cros_ui
from autotest_lib.client.cros import cros_ui_test, cryptohome, login


class login_OwnershipNotRetaken(cros_ui_test.UITest):
    version = 1

    _TEST_USER = 'example@chromium.org'
    _TEST_PASS = 'testme'

    def initialize(self, creds='$default'):
        super(login_OwnershipNotRetaken, self).initialize(
            creds, is_creating_owner=True)


    def run_once(self):
        login.wait_for_ownership()
        self.logout()
        key = open(constants.OWNER_KEY_FILE, 'rb')
        hash = hashlib.md5(key.read())
        key.close()
        mtime = os.stat(constants.OWNER_KEY_FILE).st_mtime
        # Work around until crosbug.com/139166 is fixed
        self.pyauto.ExecuteJavascriptInOOBEWebUI('Oobe.showSigninUI();'
            'window.domAutomationController.send("ok");')
        self.login(self._TEST_USER, self._TEST_PASS)
        if os.stat(constants.OWNER_KEY_FILE).st_mtime > mtime:
            raise error.TestFail("Owner key was touched on second login!")

        # Sanity check.
        key2 = open(constants.OWNER_KEY_FILE, 'rb')
        hash2 = hashlib.md5(key2.read())
        key2.close()
        if hash.hexdigest() != hash2.hexdigest():
            raise error.TestFail("Owner key was touched on second login!")


    def cleanup(self):
        super(login_OwnershipNotRetaken, self).cleanup()
        cryptohome.remove_vault(self._TEST_USER)
