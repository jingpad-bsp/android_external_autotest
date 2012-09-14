# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faftsequence import FAFTSequence

class firmware_ECSharedMem(FAFTSequence):
    """
    Servo based EC shared memory test.
    """
    version = 1

    # Delay for EC boot
    EC_BOOT_DELAY = 0.5


    def setup(self):
        # Only run in normal mode
        self.setup_dev_mode(False)

    def shared_mem_checker(self):
        match = self.send_uart_command_get_output("shmem",
                                                  ["Size:\s+([0-9-]+)\r"])[0]
        shmem_size = int(match.group(1))
        logging.info("EC shared memory size if %d bytes", shmem_size)
        if shmem_size <= 0:
            return False
        elif shmem_size <= 256:
            logging.warning("EC shared memory is less than 256 bytes")
        return True


    def jump_checker(self):
        self.send_uart_command("sysjump RW")
        time.sleep(self.EC_BOOT_DELAY)
        return self.shared_mem_checker()


    def run_once(self, host=None):
        if not self.check_ec_capability():
            return
        self.register_faft_sequence((
            {   # Step 1, check shared memory in normal operation and crash EC
                'state_checker': self.shared_mem_checker,
                'reboot_action': (self.send_uart_command, "crash unaligned")
            },
            {   # Step 2, Check shared memory after crash and system jump
                'state_checker': (lambda: self.shared_mem_checker() and
                                          self.jump_checker()),
                'reboot_action': self.sync_and_ec_reboot,
            },
            {   # Step 3, dummy step to make step 2 reboot so as to clean EC
                #         state.
            }
        ))
        self.run_faft_sequence()
