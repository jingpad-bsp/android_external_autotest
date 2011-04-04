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
        login.attempt_logout()
        key = open(constants.OWNER_KEY_FILE, 'rb')
        hash = hashlib.md5(key.read())
        key.close()
        mtime = os.stat(constants.OWNER_KEY_FILE).st_mtime
        login.refresh_login_screen()
        login.attempt_login(self._TEST_USER, self._TEST_PASS)
        try:
            utils.poll_for_condition(
                lambda: os.stat(constants.OWNER_KEY_FILE).st_mtime > mtime,
                login.TimeoutError(''),
                20)
            # If we DIDN'T time out...badness!
            raise error.TestFail("Owner key was touched on second login!")
        except login.TimeoutError, e:
            pass

        # Sanity check.
        key2 = open(constants.OWNER_KEY_FILE, 'rb')
        hash2 = hashlib.md5(key2.read())
        key2.close()
        if hash.hexdigest() != hash2.hexdigest():
            raise error.TestFail("Owner key was touched on second login!")


    def cleanup(self):
        super(login_OwnershipNotRetaken, self).cleanup()
        cryptohome.remove_vault(self._TEST_USER)
