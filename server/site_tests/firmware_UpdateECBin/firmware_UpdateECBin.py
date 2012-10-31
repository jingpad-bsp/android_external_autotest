# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import logging, os

from autotest_lib.client.common_lib import error, utils
from autotest_lib.server.cros import vboot_constants as vboot
from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_UpdateECBin(FAFTSequence):
    """
    This test verified the EC software sync. The EC binary is embedded in
    the BIOS image. On AP startup, AP verifies the EC by comparing the
    hash of the current EC with the hash of the embedded EC image. So
    updating EC is simple and we just need to change the EC binary on
    the BIOS image.

    This test requires a new EC image for update. The new EC image should
    be different with the existing EC image on the current BIOS. In normal
    cases, we use the ec_autest_image.bin from firmware_from_source.tar.bz2.
    The ec_autest_image.bin is the same binary as ec.bin but shift'ed and its
    version string has the "_shift" suffix.

    The new EC image should be specified by the new_ec argument, like:
      run_remote_tests.sh --args "new_ec=ec_autest_image.bin" ...

    The test covers RONORMAL->TWOSTOP, TWOSTOP->TWOSTOP, and
    TWOSTOP->RONORMAL updates.
    """
    version = 1


    def initialize(self, host, cmdline_args, use_pyauto=False, use_faft=True):
        # Parse arguments from command line
        dict_args = utils.args_to_dict(cmdline_args)
        if 'new_ec' not in dict_args or not os.path.isfile(dict_args['new_ec']):
            raise error.TestError(
                    'Should specify a valid new_ec image for update, like: '
                    'run_remote_tests.sh --args "new_ec=/path/to/'
                    'ec_autest_image.bin". The ec_autest_image.bin file is '
                    'included in the firmware_from_source.tar.bz2.')
        self.arg_new_ec = dict_args['new_ec']
        logging.info('The EC image to-be-updated is: %s', self.arg_new_ec)
        super(firmware_UpdateECBin, self).initialize(host, cmdline_args,
                                                     use_pyauto, use_faft)


    def setup(self, host, dev_mode=False):
        super(firmware_UpdateECBin, self).setup()
        self.backup_firmware()
        self.setup_dev_mode(dev_mode)

        temp_path = self.faft_client.get_temp_path()
        self.faft_client.setup_firmwareupdate_temp_dir()

        self.new_ec_path = os.path.join(temp_path, 'new_ec.bin')
        host.send_file(self.arg_new_ec, self.new_ec_path)


    def cleanup(self):
        self.restore_firmware()
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


    def new_ec_checker(self):
        return (self.checkers.ro_normal_checker('A', twostop=True) and
                (self.faft_client.get_EC_firmware_sha() == self.new_ec_sha))


    def run_once(self, host=None):
        if not self.check_ec_capability():
            return

        flags = self.faft_client.get_firmware_flags('a')
        if flags & vboot.PREAMBLE_USE_RO_NORMAL == 0:
            logging.info('The firmware USE_RO_NORMAL flag is disabled.')
            return

        self.register_faft_sequence((
            {   # Step 1, expected EC RO boot, update EC and disable RO flag
                'state_checker': (self.checkers.ro_normal_checker, 'A'),
                'userspace_action': self.do_ronormal_update,
                'reboot_action': self.sync_and_warm_reboot,
            },
            {   # Step 2, expected new EC and RW boot, restore the original BIOS
                'state_checker': self.new_ec_checker,
                'userspace_action': self.do_twostop_update,
                # We use warm reboot here to test the following EC behavior:
                #   If EC is already into RW before powering on the AP, the AP
                #   will need to get the EC into RO first. It does this by
                #   telling the EC to wait for the AP to shut down, reboot
                #   into RO, then power on the AP automatically.
                'reboot_action': self.sync_and_warm_reboot,
            },
            {   # Step 3, expected different EC and RW boot, enable RO flag
                'state_checker': self.new_ec_checker,
                'userspace_action': (self.faft_client.set_firmware_flags,
                                     ('a', flags)),
                'reboot_action': self.sync_and_warm_reboot,
            },
            {   # Step 4, expected EC RO boot, done
                'state_checker': (self.checkers.ro_normal_checker, 'A'),
            },
        ))
        self.run_faft_sequence()
