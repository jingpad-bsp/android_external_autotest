# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import auth_server, cros_ui_test, cryptohome
from autotest_lib.client.cros import dns_server

class login_CryptohomeIncognitoUnmounted(cros_ui_test.UITest):
    version = 1


    def __authenticator(self, email, password):
        return False


    def start_authserver(self):
        super(login_CryptohomeIncognitoUnmounted, self).start_authserver(
            authenticator=self.__authenticator)


    def run_once(self):
        if not cryptohome.is_guest_vault_mounted():
            raise error.TestFail('Expected to find a guest vault mounted via '
                                 'tmpfs.')
        self.logout()
        # Allow the command to fail, so we can handle the error here.
        if cryptohome.is_guest_vault_mounted(allow_fail=True):
            raise error.TestFail('Expected to NOT find a guest vault mounted.')
