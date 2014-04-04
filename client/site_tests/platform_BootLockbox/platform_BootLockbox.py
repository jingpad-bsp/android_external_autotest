# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cryptohome


class platform_BootLockbox(test.test):
    """ Test basic boot-lockbox functionality."""
    version = 1

    def initialize(self):
        test.test.initialize(self)
        self.data_file = '/tmp/__lockbox_test'
        open(self.data_file, mode='w').write('test_lockbox_data')

    def cleanup(self):
        os.remove(self.data_file)
        signature_file = self.data_file + ".signature"
        if os.access(signature_file, os.F_OK):
            os.remove(signature_file)
        test.test.cleanup(self)

    def _ensure_tpm_ready(self):
        status = cryptohome.get_tpm_status()
        if not status['Enabled']:
            raise error.TestNAError('Test NA because there is no TPM.')
        if not status['Owned']:
            cryptohome.take_tpm_ownership()
        status = cryptohome.get_tpm_status()
        if not status['Ready']:
            raise error.TestError('Failed to initialize TPM.')

    def _sign_lockbox(self):
        return utils.system(cryptohome.CRYPTOHOME_CMD +
                            ' --action=sign_lockbox --file=' + self.data_file,
                            ignore_status=True) == 0

    def _verify_lockbox(self):
        return utils.system(cryptohome.CRYPTOHOME_CMD +
                            ' --action=verify_lockbox --file=' + self.data_file,
                            ignore_status=True) == 0

    def _finalize_lockbox(self):
        utils.system(cryptohome.CRYPTOHOME_CMD + ' --action=finalize_lockbox')

    def run_once(self):
        self._ensure_tpm_ready()
        if not self._sign_lockbox():
            # This will fire if you forget to reboot before running the test!
            raise error.TestFail('Boot lockbox could not be signed.')
        if not self._verify_lockbox():
            raise error.TestFail('Boot lockbox could not be verified.')
        # Setup a bad signature and make sure it doesn't verify.
        open(self.data_file, mode='w').write('test_lockbox_data2')
        if self._verify_lockbox():
            raise error.TestFail('Boot lockbox verified bad data.')
        open(self.data_file, mode='w').write('test_lockbox_data')
        # Finalize and make sure we can verify but not sign.
        self._finalize_lockbox()
        if not self._verify_lockbox():
            raise error.TestFail('Boot lockbox could not be verified after '
                                 'finalization.')
        if self._sign_lockbox():
            raise error.TestFail('Boot lockbox signed after finalization.')
