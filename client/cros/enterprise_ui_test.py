# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
import logging
import os
import shutil

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error, pexpect
from autotest_lib.client.cros import cros_ui, cros_ui_test, cryptohome


class EnterpriseUITest(cros_ui_test.UITest):
    """Base class for tests requiring enterprise enrollment/unenrollment.

    The device is prepared for enrollment during initialization if required.
    The test method in derived classes can then enroll the device. The device is
    returned to initial conditions in the cleanup.

    How to derive from this class:
        - Do not override any methods in this class
        - The name of the test method should be added to the server-side
          control file.

    Pre-conditions/Post-conditions:
        - TPM is not owned
        - /home/chronos/.oobe_completed exists
    """
    version = 1

    _TPM_PASSWORD_FILE = '/var/lib/tpm_password'
    _TPM_CLEAR_LIST = ['/var/lib/whitelist', '/var/lib/tpm', '/var/lib/.tpm*',
                       '/home/.shadow/*']
    _MACHINE_INFO_FILE = '/tmp/machine-info'
    _STAGING_CHROME_FLAGS = [
        ('--device-management-url='
         'https://cros-auto.sandbox.google.com/devicemanagement/data/api'),
        '--gaia-host=gaiastaging.corp.google.com',
    ]


    def initialize(self, prod=False, enroll=False):
        """
        Args:
            prod: Whether to point to production DMServer and gaia auth server.
            enroll: Whether the test enrolls the device.
        """
        self._client_completed = False
        self._enroll = enroll
        if self._enroll:
            self.__tpm_take_ownership()
            self.__generate_machine_info_file()
        self.auto_login = False
        extra_chrome_flags = self._STAGING_CHROME_FLAGS if not prod else []
        cros_ui_test.UITest.initialize(
            self, is_creating_owner=True,
            extra_chrome_flags=extra_chrome_flags,
            subtract_extra_chrome_flags=['--skip-oauth-login'],
            chrome_test_deps=True)


    def cleanup(self):
        cros_ui_test.UITest.cleanup(self)
        if self._enroll:
            self.__tpm_clear()
        self.job.set_state('client_completed', self._client_completed)


    def __remove_files(self, list):
        """Removes files/directories in the given list if they exist.

        Args:
            list: List of file/directories that can contain wildcard characters.
        """
        paths = [item for sublist in map(glob.glob, list) for item in sublist]
        for item in paths:
            if os.path.isdir(item):
                shutil.rmtree(item)
            elif os.path.isfile(item):
                os.remove(item)


    def __tpm_clear(self):
        """Clear the TPM using a previously saved password."""
        logging.info('client: Clearing the TPM.')
        if not cryptohome.get_tpm_status()['Owned']:
            logging.info('client: TPM not owned. Skipping...')
            return
        with open(self._TPM_PASSWORD_FILE, 'r') as passwd_file:
            tpm_password = passwd_file.read().strip()
        tpm_clear = pexpect.spawn('tpm_clear')
        tpm_clear.expect('password: ')
        tpm_clear.sendline(tpm_password)
        out = tpm_clear.read().strip()
        if 'failed' in out:
            raise error.TestError('tpm_clear failed: %s' % out)
        tpm_clear.close()
        self.__remove_files(self._TPM_CLEAR_LIST)


    def __tpm_take_ownership(self):
        """Take ownership of TPM and save the password to a known file."""
        logging.info('client: Take TPM owernship.')
        tpm_status = cryptohome.get_tpm_status()
        if tpm_status['Owned']:
            if not tpm_status['Password']:
                raise error.TestError('TPM is already owned.')
        else:
            cryptohome.take_tpm_ownership()
            tpm_status = cryptohome.get_tpm_status()
            if not tpm_status['Owned']:
                raise error.TestError('Failed to take TPM ownership.')
            if not tpm_status['Password']:
                raise error.TestError('Failed to get TPM password.')
        with open(self._TPM_PASSWORD_FILE, 'w') as passwd_file:
            passwd_file.write(tpm_status['Password'])


    def __generate_machine_info_file(self):
        """Generate machine_info file needed for enrollment.

        Note: UI needs to be restarted for this to take effect.
        """
        logging.info('client: Generating /tmp/machine-info')
        # This is borrowed from src/platform/init/chromeos_startup.
        with open(self._MACHINE_INFO_FILE, 'w') as machine_info_file:
            out = utils.system_output('mosys -k smbios info system')
            machine_info_file.write(out + '\n')
            out = utils.system_output('dump_vpd_log --full --stdout')
            machine_info_file.write(out)
            os.fchmod(machine_info_file.fileno(), 0644)


    def run_once(self, subtest=None):
        """
        Args:
            subtest: Name of the test function to run.
        """
        logging.info('client: Running client test %s', subtest)
        getattr(self, subtest)()
        self._client_completed = True
