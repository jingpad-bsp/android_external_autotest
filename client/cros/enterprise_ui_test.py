# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob, logging, os, shutil

import common, cros_ui, cros_ui_test, cryptohome
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error, pexpect


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

    def __init__(self, *args, **kwargs):
      cros_ui_test.UITest.__init__(self, *args, **kwargs)
      cros_ui_test.UITest.use_chrome_deps(self)


    def initialize(self, prod=False, enroll=False):
        """
        Args:
            prod: Whether to point to production DMServer and gaia auth server.
            enroll: Whether the test enrolls the device.
        """
        self._client_completed = False
        self._enroll = enroll
        if self._enroll:
            self.__tpm_pretest_check()
            self.__tpm_take_ownership()
            self.__generate_machine_info_file()
        self.auto_login = False
        extra_chrome_flags = self._STAGING_CHROME_FLAGS if not prod else []
        cros_ui_test.UITest.initialize(
            self, is_creating_owner=True,
            extra_chrome_flags=extra_chrome_flags,
            subtract_extra_chrome_flags=['--skip-oauth-login'])


    def cleanup(self):
        cros_ui_test.UITest.cleanup(self)
        if self._enroll or self.job.get_state('client_state') == 'REBOOT':
            self.__tpm_clear()
        if self.job.get_state('client_state') == 'RUNNING':
            self.job.set_state('client_state',
                               'SUCCESS' if self._client_completed else 'ERROR')


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
        if not os.path.isfile(self._TPM_PASSWORD_FILE):
            self.job.set_state('client_state', 'UNRECOVERABLE')
            raise error.TestError(
                'TPM is owned and TPM password file %s doesn\'t exist.' %
                self._TPM_PASSWORD_FILE)
        with open(self._TPM_PASSWORD_FILE) as passwd_file:
            tpm_password = passwd_file.read().strip()
        tpm_clear = pexpect.spawn('tpm_clear')
        try:
            tpm_clear.expect('password: ')
            tpm_clear.sendline(tpm_password)
            out = tpm_clear.read().strip()
            if 'failed' in out:
                self.job.set_state('client_state', 'UNRECOVERABLE')
                raise error.TestError('tpm_clear failed: %s' % out)
        finally:
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


    def __tpm_pretest_check(self):
        """Check if the TPM is owned.

        The subtest will not be run if the TPM is owned, and the cleanup stage
        will attempt to clear the TPM using the saved password file. The server
        side is responsible for rebooting the client and rerunning the test.
        """
        tpm_status = cryptohome.get_tpm_status()
        if not tpm_status['Owned'] or tpm_status['Password']:
            logging.info('client: Pretest check passed.')
            return
        logging.info('client: TPM already owned. '
                     'Will attempt to clear TPM and request test rerun.')
        self.job.set_state('client_state', 'REBOOT')


    def run_once(self, subtest=None):
        """
        Args:
            subtest: Name of the test function to run.
        """
        if self.job.get_state('client_state') == 'RUNNING':
            logging.info('client: Running client test %s', subtest)
            getattr(self, subtest)()
            self._client_completed = True
