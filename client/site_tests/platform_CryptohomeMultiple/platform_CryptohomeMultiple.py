# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cryptohome

class platform_CryptohomeMultiple(test.test):
    version = 1
    def test_mount_single(self):
        """
        Tests mounting a single not-already-existing cryptohome. Ensures that
        the infrastructure for multiple mounts is present and active.
        """
        user = 'cryptohome-multiple-0@example.com'
        cryptohome.mount_vault(user, 'test', create=True)
        utils.require_mountpoint(cryptohome.user_path(user))
        utils.require_mountpoint(cryptohome.system_path(user))
        cryptohome.unmount_vault(user)

    def run_once(self):
        if cryptohome.is_mounted(allow_fail=True):
            raise error.TestFail('Cryptohome already mounted')
        self.test_mount_single()
