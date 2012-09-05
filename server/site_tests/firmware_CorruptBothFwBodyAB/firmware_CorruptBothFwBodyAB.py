# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_CorruptBothFwBodyAB(FAFTSequence):
    """
    Servo based both firmware body A and B corruption test.

    The expected behavior is different if the firmware preamble USE_RO_NORMAL
    flag is enabled. In the case USE_RO_NORMAL ON, the firmware corruption
    doesn't hurt the boot results since it boots the RO path directly and does
    not load and verify the RW firmware body. In the case USE_RO_NORMAL OFF,
    the firmware verification fails on loading RW firmware and enters recovery
    mode. In this case, it requires a USB disk plugged-in, which contains a
    Chrome OS test image (built by "build_image --test").
    """
    version = 1

    use_ro = False


    def ensure_normal_boot(self):
        """Ensure normal boot this time.

        If not, it may be a test failure during step 2, try to recover to
        normal mode by recovering the firmware and rebooting.
        """
        if not self.crossystem_checker(
                {'mainfw_type': ('normal', 'developer')}):
            self.run_faft_step({
                'userspace_action': (self.faft_client.run_shell_command,
                    'chromeos-firmwareupdate --mode recovery')
            })


    def setup(self, dev_mode=False):
        super(firmware_CorruptBothFwBodyAB, self).setup()
        if (self.faft_client.get_firmware_flags('a') &
                self.PREAMBLE_USE_RO_NORMAL):
            self.use_ro = True
            self.setup_dev_mode(dev_mode)
        else:
            self.assert_test_image_in_usb_disk()
            self.setup_dev_mode(dev_mode)
            self.servo.set('usb_mux_sel1', 'dut_sees_usbkey')


    def cleanup(self):
        self.ensure_normal_boot()
        super(firmware_CorruptBothFwBodyAB, self).cleanup()


    def run_once(self, host=None, dev_mode=False):
        if self.use_ro:
            # USE_RO_NORMAL flag is ON. Firmware body corruption doesn't
            # hurt the booting results.
            logging.info('The firmware USE_RO_NORMAL flag is enabled.')
            self.register_faft_sequence((
                {   # Step 1, corrupt both firmware body A and B
                    'state_checker': (self.crossystem_checker, {
                        'mainfw_type': 'developer' if dev_mode else 'normal',
                    }),
                    'userspace_action': (self.faft_client.corrupt_firmware_body,
                                         ('a', 'b')),
                },
                {   # Step 2, still expected normal/developer boot and restore
                    'state_checker': (self.crossystem_checker, {
                        'mainfw_type': 'developer' if dev_mode else 'normal',
                    }),
                    'userspace_action': (self.faft_client.restore_firmware_body,
                                         ('a', 'b')),
                },
            ))
        else:
            self.register_faft_sequence((
                {   # Step 1, corrupt both firmware body A and B
                    'state_checker': (self.crossystem_checker, {
                        'mainfw_type': 'developer' if dev_mode else 'normal',
                    }),
                    'userspace_action': (self.faft_client.corrupt_firmware_body,
                                         ('a', 'b')),
                    'firmware_action': None if dev_mode else
                                       self.wait_fw_screen_and_plug_usb,
                    'install_deps_after_boot': True,
                },
                {   # Step 2, expected recovery boot and restore firmware
                    'state_checker': (self.crossystem_checker, {
                        'mainfw_type': 'recovery',
                        'recovery_reason':
                            self.RECOVERY_REASON['RO_INVALID_RW'],
                    }),
                    'userspace_action': (self.faft_client.restore_firmware_body,
                                         ('a', 'b')),
                },
                {   # Step 3, expected normal boot, done
                    'state_checker': (self.crossystem_checker, {
                        'mainfw_type': 'developer' if dev_mode else 'normal',
                    }),
                },
            ))
        self.run_faft_sequence()
