# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_ECUsbPorts(FAFTSequence):
    """
    Servo based EC USB port control test.
    """
    version = 1


    # Delay for remote shell command call to return
    RPC_DELAY = 1

    # Delay between turning off and on USB ports
    REBOOT_DELAY = 6


    def fake_reboot_by_usb_mode_change(self):
        """
        Turn off USB ports and also kill FAFT client so that this acts like a
        reboot. If USB ports cannot be turned off or on, reboot step would
        fail.
        """
        for_all_ports_cmd = ('id=0; while ectool usbchargemode "$id" %d;' +
                             'do id=$((id+1)); sleep 0.5; done')
        ports_off_cmd = for_all_ports_cmd % 0
        ports_on_cmd = for_all_ports_cmd % 3
        cmd = ("(sleep %d; %s; sleep %d; %s)&" %
                (self.RPC_DELAY, ports_off_cmd, self.REBOOT_DELAY, ports_on_cmd))
        self.faft_client.run_shell_command(cmd)
        self.kill_remote()


    def run_once(self, host=None):
        self.register_faft_sequence((
            {   # Step 1, turn off all USB ports and then turn them on again
                'reboot_action': self.fake_reboot_by_usb_mode_change,
            },
            {   # Step 2, dummy step to make sure step 1 reboots
            }
        ))
        self.run_faft_sequence()
