# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import tpm_utils
from autotest_lib.server import autotest
from autotest_lib.server.cros.faft.cr50_test import Cr50Test


class firmware_FWMPDisableCCD(Cr50Test):
    """A test that uses cryptohome to set the FWMP flags and verifies that
    cr50 disables/enables console unlock."""
    version = 1

    FWMP_DEV_DISABLE_CCD_UNLOCK = (1 << 6)
    GSCTOOL_ERR = 'Error: rv 7, response 7'
    PASSWORD = 'Password'

    def initialize(self, host, cmdline_args, full_args):
        """Initialize servo check if cr50 exists"""
        super(firmware_FWMPDisableCCD, self).initialize(host, cmdline_args,
                full_args)

        self.host = host
        # Test CCD if servo has access to Cr50, is running with CCD v1, and has
        # testlab mode enabled.
        self.test_ccd_unlock = (hasattr(self, 'cr50') and
            self.cr50.has_command('ccdstate') and not self.ccd_lockout)

        logging.info('%sTesting CCD', '' if self.test_ccd_unlock else 'Not')
        if self.test_ccd_unlock:
            self.fast_open(enable_testlab=True)


    def try_setting_password(self, fwmp_disabled_ccd):
        """Try setting the password. FWMP should block this if set"""
        # Open the console and reset ccd, so we can set the password.
        self.cr50.send_command('ccd testlab open')
        self.cr50.send_command('ccd reset')
        try:
            self.set_ccd_password(self.PASSWORD)
            if fwmp_disabled_ccd:
                raise error.TestFail('Set password while FWMP disabled ccd')
        except error.TestFail, e:
            logging.info(e)
            if fwmp_disabled_ccd and 'set_password failed' in str(e):
                logging.info('Successfully blocked setting password')
            else:
                raise
        # Make sure the password is cleared
        self.cr50.send_command('ccd testlab open')
        self.cr50.send_command('ccd reset')


    def try_ccd_open(self, fwmp_disabled_ccd):
        """Try opening cr50 from the AP

        The FWMP flags may disable ccd. If it does, opening cr50 should fail.

        @param fwmp_disabled_ccd: True if open should fail
        """
        # Make sure the password is cleared, ccd is locked, and the device is
        # in dev mode, so the only thing that could interfere with open is the
        # FWMP.
        self.cr50.send_command('ccd testlab open')
        self.cr50.send_command('ccd reset')
        self.cr50.send_command('ccd lock')
        if 'dev_mode' not in self.cr50.get_ccd_info()['TPM']:
            self.switcher.reboot_to_mode(to_mode='dev')
        try:
            self.ccd_open_from_ap()
            if fwmp_disabled_ccd:
                raise error.TestFail('FWMP failed to prevent open')
        except error.TestFail, e:
            logging.info(e)
            raise
        if (self.cr50.get_ccd_level() == 'open') == fwmp_disabled_ccd:
            raise error.TestFail('Unexpected Open response')


    def cr50_check_lock_control(self, flags):
        """Verify cr50 lock enable/disable works as intended based on flags.

        If flags & self.FWMP_DEV_DISABLE_CCD_UNLOCK is true, lock disable should
        fail.

        This will only run during a test with access to the cr50  console

        @param flags: A string with the FWMP settings.
        """
        fwmp_disabled_ccd = not not (self.FWMP_DEV_DISABLE_CCD_UNLOCK &
                               int(flags, 16))

        if (('fwmp_lock' in self.cr50.get_ccd_info()['TPM']) !=
            fwmp_disabled_ccd):
            raise error.TestFail('Unexpected fwmp state with flags %x' % flags)

        if not self.test_ccd_unlock:
            return

        logging.info('Flags are set to %s ccd is%s permitted', flags,
                     ' not' if fwmp_disabled_ccd else '')

        self.try_setting_password(fwmp_disabled_ccd)
        self.try_ccd_open(fwmp_disabled_ccd)

        # Clear the password and relock the console
        self.cr50.send_command('ccd testlab open')
        self.cr50.send_command('ccd reset')
        self.cr50.send_command('ccd lock')


    def check_fwmp(self, flags, clear_tpm_owner):
        """Set the flags and verify ccd lock/unlock

        Args:
            flags: A string to used set the FWMP flags
            clear_tpm_owner: True if the TPM owner needs to be cleared before
                             setting the flags and verifying ccd lock/unlock
        """
        if clear_tpm_owner:
            logging.info('Clearing TPM owner')
            tpm_utils.ClearTPMOwnerRequest(self.host, wait_for_ready=True)

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
        tpm_utils.ClearTPMOwnerRequest(self.host, wait_for_ready=True)
        self.cr50_check_lock_control('0')
