# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, pexpect
from autotest_lib.client.cros import cryptohome


class factory_TPM(test.test):
    version = 1

    def __tpm_clear(self, tpm_password):
        """Clear the TPM using a previously saved password."""
        tpm_clear = pexpect.spawn('tpm_clear')
        try:
            tpm_clear.expect('password: ')
            tpm_clear.sendline(tpm_password)
            out = tpm_clear.read().strip()
            if 'failed' in out:
                raise error.TestError('tpm_clear failed: %s' % out)
        finally:
            tpm_clear.close()

    def run_once(self):
        status = cryptohome.get_tpm_status()
        if not status['Enabled']:
            raise error.TestError("TPM is not enabled.")
        if not status['Owned']:
            cryptohome.take_tpm_ownership()
        status = cryptohome.get_tpm_status()
        if status['Password'] == '':
            raise error.TestError("TPM owner password is not available. "
                                  "Boot in recovery mode to clear the TPM.")
        result = cryptohome.verify_ek()
        self.__tpm_clear(status['Password'])
        if not result:
            raise error.TestFail("TPM endorsement key is not valid.")
