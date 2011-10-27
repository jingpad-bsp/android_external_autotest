# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import os
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cryptohome

class platform_CryptohomeNonDirs(test.test):
    version = 1
    cryptohome_proxy = None

    def require_mount_fail(self, user):
        if self.cryptohome_proxy.mount(user, 'test', create=True):
            raise error.TestFail('Mount failed for %s' % user)

    def run_once(self):
        self.cryptohome_proxy = cryptohome.Cryptohome()

        # Leaf element of user path is non-dir.
        user = utils.random_username()
        path = cryptohome.user_path(user)
        utils.open_write_close(path, '')
        try:
            self.require_mount_fail(user)
        finally:
            os.remove(path)

        # Leaf element of system path is non-dir.
        user = utils.random_username()
        path = cryptohome.system_path(user)
        os.symlink('/etc', path)
        try:
            self.require_mount_fail(user)
        finally:
            os.remove(path)

        # Non-leaf element of user path is non-dir.
        user = utils.random_username()
        path = cryptohome.user_path(user)
        parent_path = os.path.dirname(path)
        utils.open_write_close(path, '')
        try:
            self.require_mount_fail(user)
        finally:
            os.remove(parent_path)

        # Non-leaf element of system path is non-dir.
        user = utils.random_username()
        path = cryptohome.system_path(user)
        parent_path = os.path.dirname(path)
        utils.open_write_close(parent_path, 'w')
        try:
            self.require_mount_fail(user)
        finally:
            os.remove(parent_path)
