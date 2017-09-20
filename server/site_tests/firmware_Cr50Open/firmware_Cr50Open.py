# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class firmware_Cr50Open(FirmwareTest):
    """Verify cr50 unlock.

    Enable the lock on cr50, run 'lock disable', and then press the power
    button until it is unlocked.
    """
    version = 1

    def initialize(self, host, cmdline_args):
        """Initialize the test"""
        super(firmware_Cr50Open, self).initialize(host, cmdline_args)

        if not hasattr(self, 'cr50'):
            raise error.TestNAError('Test can only be run on devices with '
                                    'access to the Cr50 console')
        if self.cr50.using_ccd():
            raise error.TestNAError('Use a flex cable instead of CCD cable.')

        if not self.cr50.has_command('ccdstate'):
            raise error.TestNAError('Cannot test on Cr50 with old CCD version')


    def run_once(self):
        """Lock CCD and then Open it."""
        self.cr50.ccd_set_level('lock')
        self.cr50.ccd_set_level('open')

