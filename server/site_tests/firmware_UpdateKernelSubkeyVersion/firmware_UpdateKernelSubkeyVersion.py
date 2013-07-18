# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os
from autotest_lib.server import utils
from autotest_lib.server.cros.faft_classes import FAFTSequence
from autotest_lib.client.common_lib import error


class firmware_UpdateKernelSubkeyVersion(FAFTSequence):
    """
    This test requires firmware id matches fwid of shellball
    chromeos-firmwareupdate. On runtime, this test modifies shellball and runs
    autoupdate. Check kernel subkey version after boot with firmware B, and
    then recover firmware A and B to original shellball.
    """
    version = 1

    def resign_kernel_subkey_version(self, host):
        host.send_file(os.path.join(
                           '~/trunk/src/platform/vboot_reference/scripts',
                           'keygeneration/common.sh'),
                       os.path.join(self.faft_client.updater.get_temp_path(),
                                    'common.sh'))
        host.send_file(os.path.join(
                           '~/trunk/src/third_party/autotest/files/server',
                           'site_tests/firmware_UpdateKernelSubkeyVersion',
                           'files/make_keys.sh'),
                       os.path.join(self.faft_client.updater.get_temp_path(),
                                    'make_keys.sh'))

        self.faft_client.system.run_shell_command('/bin/bash %s %s' % (
            os.path.join(self.faft_client.updater.get_temp_path(),
                         'make_keys.sh'),
            self._update_version))


    def check_kernel_subkey_version(self, expected_ver):
        actual_ver = self.faft_client.bios.get_kernel_subkey_version('a')
        if actual_ver != expected_ver:
            raise error.TestFail(
                    'Kernel subkey version should be %s, but got %s.' %
                    (expected_ver, actual_ver))
        else:
            logging.info(
                'Update success, now subkey version is %s',
                actual_ver)


    def run_bootok_and_recovery(self):
        self.faft_client.updater.run_bootok('test')
        self.check_kernel_subkey_version(self._update_version)
        self.faft_client.updater.run_recovery()


    def initialize(self, host, cmdline_args):
        dict_args = utils.args_to_dict(cmdline_args)
        self.use_shellball = dict_args.get('shellball', None)
        super(firmware_UpdateKernelSubkeyVersion, self).initialize(
            host, cmdline_args)


    def setup(self, host=None):
        self.backup_firmware()
        updater_path = self.setup_firmwareupdate_shellball(self.use_shellball)
        self.faft_client.updater.setup(updater_path)

        # Update firmware if needed
        if updater_path:
            self.set_hardware_write_protect(enable=False)
            self.faft_client.updater.run_factory_install()
            self.sync_and_warm_reboot()
            self.wait_for_client_offline()
            self.wait_for_client()

        super(firmware_UpdateKernelSubkeyVersion, self).setup()
        self._fwid = self.faft_client.updater.get_fwid()

        ver = self.faft_client.bios.get_kernel_subkey_version('a')
        logging.info('Origin version is %s', ver)
        self._update_version = ver + 1
        logging.info('Kernel subkey version will update to version %s',
            self._update_version)

        self.resign_kernel_subkey_version(host)
        self.faft_client.updater.resign_firmware(1)
        self.faft_client.updater.repack_shellball('test')


    def cleanup(self):
        self.faft_client.updater.cleanup()
        self.restore_firmware()
        self.invalidate_firmware_setup()
        super(firmware_UpdateKernelSubkeyVersion, self).cleanup()


    def run_once(self):
        self.register_faft_sequence((
            {   # Step1. Update firmware with new kernel subkey version.
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_act': 'A',
                    'tried_fwb': '0',
                    'fwid': self._fwid
                }),
                'userspace_action': (
                    self.faft_client.updater.run_autoupdate,
                    'test'
                ),
            },
            {   # Step2. Check firmware data key version and Rollback
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_act': 'B',
                    'tried_fwb': '1'
                }),
                'userspace_action': (self.run_bootok_and_recovery),
            },
            {   # Step3, Check Rollback version
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_act': 'A',
                    'tried_fwb': '0',
                    'fwid': self._fwid
                }),
                'userspace_action':(self.check_kernel_subkey_version,
                                    self._update_version-1)
            }
        ))
        self.run_faft_sequence()
