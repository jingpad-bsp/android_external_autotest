# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os
from autotest_lib.server import utils
from autotest_lib.server.cros.faftsequence import FAFTSequence
from autotest_lib.client.common_lib import error


class firmware_UpdateFirmwareDataKeyVersion(FAFTSequence):
    """
    This test requires firmware id matches fwid of shellball
    chromeos-firmwareupdate. On runtime, this test modifies shellball and runs
    autoupdate. Check firmware datakey version after boot with firmware B, and
    then recover firmware A and B to original shellball.
    """
    version = 1

    def resign_datakey_version(self, host):
        host.send_file(os.path.join(
                            '~/trunk/src/platform/vboot_reference/scripts',
                            'keygeneration/common.sh'),
                       os.path.join(self.faft_client.get_temp_path(),
                                     'common.sh'))
        host.send_file(os.path.join('~/trunk/src/third_party/autotest/files/',
                                    'server/site_tests',
                                    'firmware_UpdateFirmwareDataKeyVersion',
                                    'files/make_keys.sh'),
                       os.path.join(self.faft_client.get_temp_path(),
                                    'make_keys.sh'))

        self.faft_client.run_shell_command('/bin/bash %s %s' % (
             os.path.join(self.faft_client.get_temp_path(), 'make_keys.sh'),
             self._update_version))


    def check_firmware_datakey_version(self, expected_ver):
        actual_ver = self.faft_client.retrieve_firmware_datakey_version('a')
        if actual_ver != expected_ver:
            raise error.TestFail(
                'Firmware data key version should be %s, but got %s.'
                % (expected_ver, actual_ver))
        else:
            logging.info(
                'Update success, now datakey version is %s' % actual_ver)


    def run_bootok_and_recovery(self):
        self.faft_client.run_firmware_bootok('test')
        self.check_firmware_datakey_version(self._update_version)
        self.faft_client.run_firmware_recovery()


    def initialize(self, host, cmdline_args, use_pyauto=False, use_faft=True):
        dict_args = utils.args_to_dict(cmdline_args)
        self.use_shellball = dict_args.get('shellball', None)
        super(firmware_UpdateFirmwareDataKeyVersion, self).initialize(
            host, cmdline_args, use_pyauto, use_faft)


    def setup(self, host=None):
        self.backup_firmware()
        updater_path = self.setup_firmwareupdate_shellball(self.use_shellball)
        self.faft_client.setup_firmwareupdate_temp_dir(updater_path)

        # Update firmware if needed
        if updater_path:
            self.faft_client.run_firmware_factory_install()
            self.sync_and_warm_reboot()
            self.wait_for_client_offline()
            self.wait_for_client()

        super(firmware_UpdateFirmwareDataKeyVersion, self).setup()

        self._fwid = self.faft_client.retrieve_shellball_fwid()

        actual_ver = self.faft_client.retrieve_firmware_datakey_version('a')
        logging.info('Origin version is %s' % actual_ver)
        self._update_version = actual_ver + 1
        logging.info('Firmware version will update to version %s'
            % self._update_version)

        self.resign_datakey_version(host)
        self.faft_client.resign_firmware(1)
        self.faft_client.repack_firmwareupdate_shellball('test')


    def cleanup(self):
        self.faft_client.cleanup_firmwareupdate_temp_dir()
        self.restore_firmware()
        super(firmware_UpdateFirmwareDataKeyVersion, self).cleanup()


    def run_once(self, host=None):
        self.register_faft_sequence((
            {   # Step1. Update firmware with new datakey version.
                'state_checker': (self.crossystem_checker, {
                    'mainfw_act': 'A',
                    'mainfw_type': 'developer',
                    'tried_fwb': '0',
                    'fwid': self._fwid
                }),
                'userspace_action': (
                     self.faft_client.run_firmware_autoupdate,
                     'test'
                ),
                'firmware_action': (self.wait_fw_screen_and_ctrl_d)
            },
            {   # Step2. Check firmware data key version and Rollback.
                'state_checker': (self.crossystem_checker, {
                    'mainfw_act': 'B',
                    'tried_fwb': '1'
                }),
                'userspace_action': (self.run_bootok_and_recovery),
                'firmware_action': (self.wait_fw_screen_and_ctrl_d)

            },
            {   # Step3, Check Rollback version.
                'state_checker': (self.crossystem_checker, {
                    'mainfw_act': 'A',
                    'tried_fwb': '0',
                    'fwid': self._fwid
                }),
                'userspace_action':(self.check_firmware_datakey_version,
                                    self._update_version-1)
            }
        ))
        self.run_faft_sequence()
