# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class firmware_Cr50Unlock(FirmwareTest):
    """Verify cr50 unlock.

    Enable the lock on cr50, run 'lock disable', and then press the power
    button until it is unlocked.
    """
    version = 1

    def initialize(self, host, cmdline_args):
        """Initialize servo and check that it has access to cr50 with ccd"""
        super(firmware_Cr50Unlock, self).initialize(host, cmdline_args)

        if not hasattr(self, 'cr50'):
            raise error.TestNAError('Test can only be run on devices with '
                                    'access to the Cr50 console')
        if self.cr50.using_ccd():
            raise error.TestNAError('Use a flex cable instead of CCD cable.')


    def run_once(self):
        """Verify cr50 lock behavior on v1 images and v0 images"""
        if self.cr50.has_command('ccdstate'):
            self.cr50.set_ccd_level('lock')
            self.cr50.set_ccd_level('unlock')
        else:
            # pre-v1, cr50 cannot be unlocked. Make sure that's true
            logging.info(self.cr50.send_command_get_output('lock disable',
                    ['Access Denied\s+Usage: lock']))
            logging.info('Cr50 cannot be unlocked with ccd v0')

