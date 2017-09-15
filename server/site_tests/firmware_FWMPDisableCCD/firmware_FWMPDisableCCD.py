# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import tpm_utils
from autotest_lib.server import autotest
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class firmware_FWMPDisableCCD(FirmwareTest):
    """A test that uses cryptohome to set the FWMP flags and verifies that
    cr50 disables/enables console unlock."""
    version = 1

    FWMP_DEV_DISABLE_CCD_UNLOCK = (1 << 6)


    def initialize(self, host, cmdline_args):
        """Initialize servo check if cr50 exists"""
        super(firmware_FWMPDisableCCD, self).initialize(host, cmdline_args)

        self.host = host
        # Test CCD if servo has access to Cr50, is running with CCD v1, and has
        # testlab mode enabled.
        self.test_ccd_unlock = (hasattr(self, "cr50") and
            self.cr50.has_command('ccdstate') and
            self.servo.get('cr50_testlab') == 'enabled')

        logging.info('%sTesting CCD Unlock', '' if self.test_ccd_unlock else
            'Not ')


    def try_ccd_level_change(self, level, fwmp_disabled_unlock):
        """Try changing the ccd privilege level

        The FWMP flags may disable ccd. If they do, unlocking or opening CCD
        should fail.

        @param level: the ccd privilege level: open or unlock.
        @param fwmp_disabled_unlock: True if the unlock process should fail
        """
        # Verify that the ccd disable flag is set
        self.cr50_check_fwmp_flag(fwmp_disabled_unlock)

        # Enable the lock
        self.cr50.ccd_set_level('lock')
        try:
            self.cr50.ccd_set_level(level)
            success = True
            logging.info('Cr50 CCD %s Succeeded', level)
        except error.TestFail, e:
            logging.info('Cr50 CCD %s Failed', level)
            success = False

        if fwmp_disabled_unlock == success:
            raise error.TestFail('Did not expect %s %s with fwmp unlock %sabled'
                                 % (level, 'success' if success else 'fail',
                                 'dis' if fwmp_disabled_unlock else 'en'))

        # Verify that the ccd disable flag is still set
        self.cr50_check_fwmp_flag(fwmp_disabled_unlock)


    def cr50_check_fwmp_flag(self, fwmp_disabled_unlock):
        """Verify cr50 thinks the flag is set or cleared"""
        response = 'Console unlock%s allowed' % (' not' if fwmp_disabled_unlock
                                                 else '')
        self.cr50.send_command('ccd testlab open')
        self.cr50.send_command_get_output('sysrst pulse', [response])


    def cr50_check_lock_control(self, flags):
        """Verify cr50 lock enable/disable works as intended based on flags.

        If flags & self.FWMP_DEV_DISABLE_CCD_UNLOCK is true, lock disable should
        fail.

        This will only run during a test with access to the cr50  console

        @param flags: A string with the FWMP settings.
        """
        if not self.test_ccd_unlock:
            return

        fwmp_disabled_unlock = (self.FWMP_DEV_DISABLE_CCD_UNLOCK &
                               int(flags, 16))

        logging.info('Flags are set to %s ccd level change is %s', flags,
                     'disabled' if fwmp_disabled_unlock else 'enabled')

        # The ccd privilege level can be changed to unlock or open. Make sure
        # that the fwmp setting affects both the same.
        self.try_ccd_level_change('unlock', fwmp_disabled_unlock)
        self.try_ccd_level_change('open', fwmp_disabled_unlock)



    def check_fwmp(self, flags, clear_tpm_owner):
        """Set the flags and verify ccd lock/unlock

        Args:
            flags: A string to used set the FWMP flags
            clear_tpm_owner: True if the TPM owner needs to be cleared before
                             setting the flags and verifying ccd lock/unlock
        """
        if clear_tpm_owner:
            logging.info('Clearing TPM owner')
            tpm_utils.ClearTPMOwnerRequest(self.host)

        logging.info('setting flags to %s', flags)
        autotest.Autotest(self.host).run_test('firmware_SetFWMP', flags=flags,
                fwmp_cleared=clear_tpm_owner, check_client_result=True)

        # Verify ccd lock/unlock with the current flags works as intended.
        self.cr50_check_lock_control(flags)


    def run_once(self):
        """Verify FWMP disable with different flag values"""
        self.check_fwmp('0xaa00', True)
        # Verify that the flags can be changed on the same boot
        self.check_fwmp('0xbb00', False)

        # Verify setting FWMP_DEV_DISABLE_CCD_UNLOCK disables ccd
        self.check_fwmp(hex(self.FWMP_DEV_DISABLE_CCD_UNLOCK), True)

        # 0x41 is the flag setting when dev boot is disabled. Make sure that
        # nothing unexpected happens.
        self.check_fwmp('0x41', True)

        # Clear the TPM owner and verify lock can still be enabled/disabled when
        # the FWMP has not been created
        tpm_utils.ClearTPMOwnerRequest(self.host)
        self.cr50_check_lock_control('0')
