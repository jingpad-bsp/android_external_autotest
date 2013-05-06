# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.server.cros.faftsequence import FAFTSequence

class firmware_ECSharedMem(FAFTSequence):
    """
    Servo based EC shared memory test.
    """
    version = 1


    def setup(self):
        super(firmware_ECSharedMem, self).setup()
        # Only run in normal mode
        self.setup_dev_mode(False)


    def shared_mem_checker(self):
        match = self.ec.send_command_get_output("shmem",
                                                ["Size:\s+([0-9-]+)\r"])[0]
        shmem_size = int(match[1])
        logging.info("EC shared memory size if %d bytes", shmem_size)
        if shmem_size <= 0:
            return False
        elif shmem_size <= 256:
            logging.warning("EC shared memory is less than 256 bytes")
        return True


    def jump_checker(self):
        self.ec.send_command("sysjump RW")
        time.sleep(self.delay.ec_boot_to_console)
        return self.shared_mem_checker()


    def run_once(self):
        if not self.check_ec_capability():
            raise error.TestNAError("Nothing needs to be tested on this device")
        self.register_faft_sequence((
            {   # Step 1, check shared memory in normal operation and crash EC
                'state_checker': self.shared_mem_checker,
                'reboot_action': (self.ec.send_command, "crash unaligned")
            },
            {   # Step 2, Check shared memory after crash and system jump
                'state_checker': [self.shared_mem_checker, self.jump_checker],
                'reboot_action': self.sync_and_ec_reboot,
            },
            {   # Step 3, dummy step to make step 2 reboot so as to clean EC
                #         state.
            }
        ))
        self.run_faft_sequence()
