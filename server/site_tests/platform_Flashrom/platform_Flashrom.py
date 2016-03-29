# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re
import os

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class platform_Flashrom(FirmwareTest):
    """
    Test flashrom works correctly by calling
    chromeos-firmwareupdate --mode=recovery.
    """
    version = 1


    def initialize(self, host, cmdline_args):
        # This test assume the system already have the latest RW from
        # shellball.  You should run chromeos-firmware --mode=factory.
        # Device should have WP disable.

        # Parse arguments from command line
        dict_args = utils.args_to_dict(cmdline_args)
        super(platform_Flashrom, self).initialize(host, cmdline_args)
        self.switcher.setup_mode('dev')

    def run_cmd(self, command, checkfor=''):
        """
        Log and execute command and return the output.

        @param command: Command to execute on device.
        @param checkfor: If not emmpty, fail test if checkfor not in output.
        @returns the output of command.
        """
        logging.info('Execute %s', command)
        output = self.faft_client.system.run_shell_command_get_output(command)
        logging.info('Output %s', output)
        if checkfor and checkfor not in ' '.join(output):
            raise error.TestFail('Expect %s in output of %s' %
                                 (checkfor, ' '.join(output)))
        return output

    def _check_wp_disable(self):
        """Check firmware is write protect disabled."""
        self.run_cmd('flashrom -p host --wp-status', checkfor='is disabled')
        if self.faft_config.chrome_ec:
            self.run_cmd('flashrom -p ec --wp-status', checkfor='is disabled')
        if self.faft_config.chrome_usbpd:
            self.run_cmd('flashrom -p ec:dev=1 --wp-status',
                         checkfor='is disabled')

    def run_once(self, dev_mode=True):
        # 1) Check SW WP is disabled.
        self._check_wp_disable()

        # Output location on DUT.
        # Set if you want to preserve output content for debug.
        tmpdir = os.getenv('DUT_TMPDIR')
        if not tmpdir: tmpdir = '/tmp'

        # 2) Erase RW section B.  Needed CL 329549 starting with R51-7989.0.0.
        self.run_cmd('flashrom -E -i RW_SECTION_B', 'SUCCESS')

        # 3) Reinstall RW B (Test flashrom)
        self.run_cmd('chromeos-firmwareupdate --mode=recovery',
                     '(recovery) completed.')

        # 4) Check that device can be rebooted.
        self.switcher.mode_aware_reboot()

        # 5) Compare flash section B vs shellball section B
        # 5.1) Extract shellball RW section B.
        outdir = self.run_cmd('chromeos-firmwareupdate --sb_extract')[-1]
        shball_path = outdir.split()[-1]
        shball_bios = os.path.join(shball_path, 'bios.bin')
        shball_rw_b = os.path.join(shball_path, 'shball_rw_b.bin')

        # Extract RW B, offset detail
        # /src/platform/vboot_reference/tests/futility/data_fmap_expect_p.txt
        self.run_cmd('dd bs=1 skip=3080192 count=983040 if=%s of=%s 2>&1'
                     % (shball_bios, shball_rw_b), '983040 bytes')

        # 5.2) Extract flash RW section B.
        rw_b2 = os.path.join(tmpdir, 'rw_b2.bin')
        self.run_cmd('flashrom -r -i RW_SECTION_B:%s' % rw_b2, 'SUCCESS')

        # 5.3) Compare output of 5.1 vs 5.2
        result_output = self.run_cmd('cmp %s %s' % (shball_rw_b, rw_b2))
        logging.info('cmp %s %s == %s', shball_rw_b, rw_b2, result_output)

        # 6) Report result.
        if ''.join(result_output) != '':
            raise error.TestFail('Mismatch between %s and %s' % (rw_b, rw_b2))
