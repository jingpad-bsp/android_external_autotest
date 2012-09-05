# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import logging, os

from autotest_lib.client.common_lib import error, utils
from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_UpdateECBin(FAFTSequence):
    """
    This test verified the EC software sync. The EC binary is embedded in
    the BIOS image. On AP startup, AP verifies the EC by comparing the
    hash of the current EC with the hash of the embedded EC image. So
    updating EC is simple and we just need to change the EC binary on
    the BIOS image.

    A new EC image should be specified by the new_ec argument, like:
      -a "new_ec=ec_autest_image.bin"

    The test covers RONORMAL->TWOSTOP, TWOSTOP->TWOSTOP, and
    TWOSTOP->RONORMAL updates.
    """
    version = 1

    PREAMBLE_USE_RO_NORMAL = 1


    def ensure_fw_a_boot(self):
        """Ensure firmware A boot this time."""
        if not self.crossystem_checker({'mainfw_act': 'A', 'tried_fwb': '0'}):
            self.run_faft_step({
                'userspace_action': (self.faft_client.run_shell_command,
                    'chromeos-firmwareupdate --mode recovery')
            })


    def initialize(self, host, cmdline_args, use_pyauto=False, use_faft=True):
        # Parse arguments from command line
        dict_args = utils.args_to_dict(cmdline_args)
        if 'new_ec' not in dict_args:
            raise error.TestError('Should specify a new_ec image for update, '
                                  'e.g. -a "new_ec=ec_autest_image.bin".')
        self.arg_new_ec = dict_args['new_ec']
        logging.info('The EC image to-be-updated is: %s' % self.arg_new_ec)
        super(firmware_UpdateECBin, self).initialize(host, cmdline_args,
                                                     use_pyauto, use_faft)


    def setup(self, host, dev_mode=False):
        super(firmware_UpdateECBin, self).setup()
        self.setup_dev_mode(dev_mode)
        self.ensure_fw_a_boot()

        temp_path = self.faft_client.get_temp_path()
        self.faft_client.setup_firmwareupdate_temp_dir()

        self.old_bios_path = os.path.join(temp_path, 'old_bios.bin')
        self.faft_client.dump_firmware(self.old_bios_path)

        self.new_ec_path = os.path.join(temp_path, 'new_ec.bin')
        host.send_file(self.arg_new_ec, self.new_ec_path)


    def cleanup(self):
        self.ensure_fw_a_boot()
        super(firmware_UpdateECBin, self).cleanup()


    def do_ronormal_update(self):
        self.faft_client.setup_EC_image(self.new_ec_path)
        self.new_ec_sha = self.faft_client.get_EC_image_sha()
        self.faft_client.update_EC_from_image('a', 0)


    def do_twostop_update(self):
        # We update the original BIOS image back. This BIOS image contains
        # the original EC binary. But set RW boot. So it is a TWOSTOP ->
        # TWOSTOP update.
        self.faft_client.write_firmware(self.old_bios_path)
        self.faft_client.set_firmware_flags('a', 0)


    def run_once(self, host=None):
        if not self.check_ec_capability():
            return

        flags = self.faft_client.get_firmware_flags('a')
        if flags & self.PREAMBLE_USE_RO_NORMAL == 0:
            logging.info('The firmware USE_RO_NORMAL flag is disabled.')
            return

        self.register_faft_sequence((
            {   # Step 1, expected EC RO boot, update EC and disable RO flag
                'state_checker': (self.ro_normal_checker, 'A'),
                'userspace_action': self.do_ronormal_update,
                'reboot_action': self.sync_and_warm_reboot,
            },
            {   # Step 2, expected new EC and RW boot, restore the original BIOS
                'state_checker': (
                    lambda: self.ro_normal_checker('A', twostop=True) and
                            (self.faft_client.get_EC_firmware_sha() ==
                                 self.new_ec_sha)),
                'userspace_action': self.do_twostop_update,
                # We use warm reboot here to test the following EC behavior:
                #   If EC is already into RW before powering on the AP, the AP
                #   will need to get the EC into RO first. It does this by
                #   telling the EC to wait for the AP to shut down, reboot
                #   into RO, then power on the AP automatically.
                'reboot_action': self.sync_and_warm_reboot,
            },
            {   # Step 3, expected different EC and RW boot, enable RO flag
                'state_checker': (
                    lambda: self.ro_normal_checker('A', twostop=True) and
                            (self.faft_client.get_EC_firmware_sha() !=
                                 self.new_ec_sha)),
                'userspace_action': (self.faft_client.set_firmware_flags,
                                     'a', flags),
                'reboot_action': self.sync_and_warm_reboot,
            },
            {   # Step 4, expected EC RO boot, done
                'state_checker': (self.ro_normal_checker, 'A'),
            },
        ))
        self.run_faft_sequence()
