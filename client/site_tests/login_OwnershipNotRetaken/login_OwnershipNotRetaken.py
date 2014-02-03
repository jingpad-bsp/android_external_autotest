# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib, os

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import constants, cryptohome, login


class login_OwnershipNotRetaken(test.test):
    """Subsequent logins after the owner must not clobber the owner's key."""
    version = 2

    _TEST_USER = 'example@chromium.org'
    _TEST_PASS = 'testme'


    def run_once(self):
        # Sign in. Sign out happens automatically when cr goes out of scope.
        with chrome.Chrome() as cr:
            login.wait_for_ownership()

        key = open(constants.OWNER_KEY_FILE, 'rb')
        hash = hashlib.md5(key.read())
        key.close()
        mtime = os.stat(constants.OWNER_KEY_FILE).st_mtime

        # Sign in/sign out as a second user.
        with chrome.Chrome(username=self._TEST_USER,
                           password=self._TEST_PASS) as cr:
            pass

        # Checking mtime to see if key file was touched during second sign in.
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
