# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from autotest_lib.server import utils
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest
from autotest_lib.client.common_lib import error


class firmware_UpdateFirmwareVersion(FirmwareTest):
    """
    Servo based firmware update test which checks the firmware version.

    This test requires a USB disk plugged-in, which contains a Chrome OS
    install shim (built by "build_image factory_install"). The firmware id of
    the current running firmware must matches the system shellball's, or user
    can provide a shellball to do this test. In this way, the client will be
    update with the given shellball first. On runtime, this test modifies the
    firmware version of the shellball and runs autoupdate. Check firmware
    version after boot with firmware B, and then recover firmware A and B to
    original shellball.
    """
    version = 1

    def check_firmware_version(self, expected_ver):
        actual_ver = self.faft_client.bios.get_version('a')
        actual_tpm_fwver = self.faft_client.tpm.get_firmware_version()
        if actual_ver != expected_ver or actual_tpm_fwver != expected_ver:
            raise error.TestFail(
                'Firmware version should be %s,'
                'but got (fwver, tpm_fwver) = (%s, %s).' %
                (expected_ver, actual_ver, actual_tpm_fwver))
        else:
            logging.info(
                'Update success, now version is %s',
                actual_ver)

    def check_version_and_run_recovery(self):
        self.check_firmware_version(self._update_version)
        self.faft_client.updater.run_recovery()

    def initialize(self, host, cmdline_args):
        dict_args = utils.args_to_dict(cmdline_args)
        self.use_shellball = dict_args.get('shellball', None)
        super(firmware_UpdateFirmwareVersion, self).initialize(
            host, cmdline_args)
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

        self.setup_usbkey(usbkey=True, host=True, install_shim=True)
        self.setup_dev_mode(dev_mode=False)
        self._fwid = self.faft_client.updater.get_fwid()

        actual_ver = self.faft_client.bios.get_version('a')
        logging.info('Origin version is %s', actual_ver)
        self._update_version = actual_ver + 1
        logging.info('Firmware version will update to version %s',
                     self._update_version)

        self.faft_client.updater.resign_firmware(self._update_version)
        self.faft_client.updater.repack_shellball('test')

    def cleanup(self):
        self.faft_client.updater.cleanup()
        self.restore_firmware()
        self.invalidate_firmware_setup()
        super(firmware_UpdateFirmwareVersion, self).cleanup()

    def run_once(self):
        logging.info("Update firmware with new version.")
        self.check_state((self.checkers.crossystem_checker, {
                          'fwid': self._fwid
                          }))
        self.check_state((self.checkers.fw_tries_checker, 'A'))
        self.faft_client.updater.run_autoupdate('test')
        self.reboot_warm()

        logging.info("Copy firmware form B to A.")
        self.check_state((self.checkers.fw_tries_checker, 'B'))
        self.faft_client.updater.run_bootok('test')
        self.reboot_warm()

        logging.info("Check firmware and TPM version, then recovery.")
        self.check_state((self.checkers.fw_tries_checker, 'A'))
        self.check_version_and_run_recovery()
        self.do_reboot_action(self.reboot_with_factory_install_shim)
        self.wait_for_kernel_up()

        logging.info("Check Rollback version.")
        self.check_state((self.checkers.crossystem_checker, {
                          'fwid': self._fwid
                          }))
        self.check_state((self.checkers.fw_tries_checker, 'A'))
        self.check_firmware_version(self._update_version - 1)
