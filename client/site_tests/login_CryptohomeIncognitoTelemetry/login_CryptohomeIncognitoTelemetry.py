# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

#pylint: disable-msg=C0111

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import cryptohome

class login_CryptohomeIncognitoTelemetry(test.test):
    version = 1


    def run_once(self):
        try:
            with chrome.Chrome(logged_in=False):
                if not cryptohome.is_guest_vault_mounted():
                    raise error.TestFail('Expected to find a guest vault '
                                         'mounted via tmpfs.')
            # Allow the command to fail, so we can handle the error here.
            if cryptohome.is_guest_vault_mounted(allow_fail=True):
                raise error.TestFail('Expected to NOT find a guest vault '
                                     'mounted.')
        # TODO(achuith, dennisjeffrey): Make this more fine-grained.
        # See crbug.com/225542.
        except Exception as err:
            raise error.TestFailRetry(err)
