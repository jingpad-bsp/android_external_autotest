# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faft.faft_classes import FAFTSequence


class firmware_TPMVersionCheck(FAFTSequence):
    """
    crossystem check of reported TPM version.

    Replacement for test '1.1.9 TPM_version_in_Crossystem [tcm:6762253]'.
    """
    version = 1


    def initialize(self, host, cmdline_args, dev_mode=False, ec_wp=None):
        super(firmware_TPMVersionCheck, self).initialize(host, cmdline_args,
                                                         ec_wp=ec_wp)
        self.setup_dev_mode(dev_mode)
        self.setup_usbkey(usbkey=False)


    def run_once(self):
        if not self.checkers.crossystem_checker({
                    'tpm_fwver': '0x00010001',
                    'tpm_kernver': '0x00010001', }):
            raise error.TestFail('tpm version keys reported by '
                                 'crossystem are not as expected.')
