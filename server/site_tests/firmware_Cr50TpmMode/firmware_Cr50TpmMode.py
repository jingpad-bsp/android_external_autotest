# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import cr50_utils
from autotest_lib.server.cros.faft.cr50_test import Cr50Test


class firmware_Cr50TpmMode(Cr50Test):
    """Verify TPM disabling and getting back enabled after reset."""
    version = 1

    def get_tpm_mode(self):
        """Query the current TPM mode."""
        return cr50_utils.GSCTool(self.host, ['-a', '-m']).stdout.strip()

    def set_tpm_mode(self, disable_tpm):
        """Disable or Enable TPM mode.

        Args:
            disable_tpm: Disable TPM if True.
                         Enable (or Confirm Enabling) otherwise.
        """
        mode_param = 'disable' if disable_tpm else 'enable'
        return cr50_utils.GSCTool(self.host,
                 ['-a', '-m', mode_param]).stdout.strip()

    def tpm_ping(self):
        """Check TPM responsiveness by running tpm_version."""
        return self.host.run('tpm_version').stdout.strip()

    def run_test_tpm_mode(self, disable_tpm):
        """Run a test for the case of either disabling TPM or enabling.

        Args:
            disable_tpm: Disable TPM if True. Enable TPM otherwise.
        """
        # Reset the device.
        logging.info('Reset')
        self.servo.get_power_state_controller().reset()
        self.switcher.wait_for_client()

        # Query TPM mode, which should be 'enabled (0)'.
        logging.info('Get TPM Mode')
        output_log = self.get_tpm_mode()
        logging.info(output_log)
        if output_log != 'TPM Mode: enabled (0)':
            raise error.TestFail('Failure in reading TPM mode after reset')

        # Check that TPM is enabled.
        self.tpm_ping()
        logging.info('Checked TPM is enabled')

        # Change TPM Mode
        logging.info('Set TPM Mode')
        output_log = self.set_tpm_mode(disable_tpm)
        logging.info(output_log)

        # Check the result of TPM Mode.
        if disable_tpm:
            if output_log != 'TPM Mode: disabled (2)':
                raise error.TestFail('Failure in disabling TPM: %s' %
                        output_log)

            # Check that TPM is disabled. The run should fail.
            try:
                result = self.tpm_ping()
            except error.AutoservRunError:
                logging.info('Checked TPM is disabled')
            else:
                raise error.TestFail('Unexpected TPM response: %s' % result)
        else:
            if output_log != 'TPM Mode: enabled (1)':
                raise error.TestFail('Failure in enabling TPM: %s' % output_log)

            # Check the TPM is enabled still.
            self.tpm_ping()
            logging.info('Checked TPM is enabled')

            # Subsequent set-TPM-mode vendor command should fail.
            try:
                output_log = self.set_tpm_mode(not disable_tpm)
            except error.AutoservRunError:
                logging.info('Expected failure in disabling TPM mode');
            else:
                raise error.TestFail('Unexpected result in disabling TPM mode:'
                        ' %s' % output_log)

    def run_once(self):
        """Test Disabling TPM and Enabling TPM"""
        # Test 1. Disabling TPM
        logging.info('Disabling TPM')
        self.run_test_tpm_mode(True)

        # Test 2. Enabling TPM
        logging.info('Enabling TPM')
        self.run_test_tpm_mode(False)
