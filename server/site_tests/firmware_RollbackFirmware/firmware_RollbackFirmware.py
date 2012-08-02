# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_RollbackFirmware(FAFTSequence):
    """
    Servo based firmware rollback test.

    This test requires a USB disk plugged-in, which contains a Chrome OS test
    image (built by "build_image --test"). On runtime, this test rollbacks
    firmware A and results firmware B boot. It then rollbacks firmware B and
    results recovery boot.
    """
    version = 1


    def ensure_normal_boot(self):
        """Ensure normal mode boot this time.

        If not, it may be a test failure during step 2 or 3, try to recover to
        normal mode by recovering the firmware and rebooting.
        """
        if not self.crossystem_checker(
                {'mainfw_type': ('normal', 'developer')}):
            self.run_faft_step({
                'userspace_action': (self.faft_client.run_shell_command,
                    'chromeos-firmwareupdate --mode recovery')
            })


    def setup(self, dev_mode=False):
        super(firmware_RollbackFirmware, self).setup()
        self.assert_test_image_in_usb_disk()
        self.setup_dev_mode(dev_mode)
        self.servo.set('usb_mux_sel1', 'dut_sees_usbkey')
        self.clear_gbb_flags(self.GBB_FLAG_DISABLE_FW_ROLLBACK_CHECK)


    def cleanup(self):
        self.ensure_normal_boot()
        super(firmware_RollbackFirmware, self).cleanup()


    def run_once(self, host=None, dev_mode=False):
        # Recovery reason RW_FW_ROLLBACK available after Alex/ZGB.
        if self.faft_client.get_platform_name() in ('Mario', 'Alex', 'ZGB'):
            recovery_reason = self.RECOVERY_REASON['RO_INVALID_RW']
        else:
            recovery_reason = self.RECOVERY_REASON['RW_FW_ROLLBACK']

        self.register_faft_sequence((
            {   # Step 1, rollbacks firmware A.
                'state_checker': (self.crossystem_checker, {
                    'mainfw_act': 'A',
                    'mainfw_type': 'developer' if dev_mode else 'normal',
                    'tried_fwb': '0',
                }),
                'userspace_action': (self.faft_client.move_firmware_backward,
                                     'a'),
            },
            {   # Step 2, expected firmware B boot and rollbacks firmware B.
                'state_checker': (self.crossystem_checker, {
                    'mainfw_act': 'B',
                    'mainfw_type': ('normal', 'developer'),
                    'tried_fwb': '0',
                }),
                'userspace_action': (self.faft_client.move_firmware_backward,
                                     'b'),
                'firmware_action': None if dev_mode else
                                   self.wait_fw_screen_and_plug_usb,
                'install_deps_after_boot': True,
            },
            {   # Step 3, expected recovery boot and restores firmware A and B.
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': 'recovery',
                    'recovery_reason' : recovery_reason,
                }),
                'userspace_action': (self.faft_client.move_firmware_forward,
                                     ('a', 'b')),
            },
            {   # Step 4, expected firmware A boot and done.
                'state_checker': (self.crossystem_checker, {
                    'mainfw_act': 'A',
                    'mainfw_type': 'developer' if dev_mode else 'normal',
                    'tried_fwb': '0',
                }),
            },
        ))
        self.run_faft_sequence()
