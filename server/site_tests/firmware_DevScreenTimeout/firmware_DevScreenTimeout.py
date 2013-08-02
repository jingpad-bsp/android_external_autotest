# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faft.faft_classes import FAFTSequence


class firmware_DevScreenTimeout(FAFTSequence):
    """
    Servo based developer firmware screen timeout test.

    When booting in developer mode, the firmware shows a screen to warn user
    the disk image is not secured. If a user press Ctrl-D or a timeout reaches,
    it will boot to developer mode. This test is to verify the timeout period.

    This test tries to boot the system in developer mode twice.
    The first one will repeatly press Ctrl-D on booting in order to reduce
    the time on developer warning screen. The second one will do nothing and
    wait the developer screen timeout. The time difference of these two boots
    is close to the developer screen timeout.
    """
    version = 1

    CTRL_D_REPEAT_COUNT = 10
    CTRL_D_REPEAT_DELAY = 0.5

    # We accept 5s timeout margin as we need 5s to ensure client is offline.
    # If the margin is too small and firmware initialization is too fast,
    # the test will fail incorrectly.
    TIMEOUT_MARGIN = 5

    fw_time_record = {}


    def ctrl_d_repeatedly(self):
        """Press Ctrl-D repeatedly."""
        for _ in range(self.CTRL_D_REPEAT_COUNT):
            self.press_ctrl_d()
            time.sleep(self.CTRL_D_REPEAT_DELAY)


    def record_fw_boot_time(self, tag):
        """Record the current firmware boot time with the tag.

        Args:
          tag: A tag about this boot.

        Raises:
          error.TestError: If the firmware-boot-time file does not exist.
        """
        [fw_time] = self.faft_client.system.run_shell_command_get_output(
                'cat /tmp/firmware-boot-time')
        logging.info('Got firmware boot time: %s', fw_time)
        if fw_time:
            self.fw_time_record[tag] = float(fw_time)
        else:
            raise error.TestError('Failed to get the firmware boot time.')


    def check_timeout_period(self):
        """Check the firmware screen timeout period matches our spec.

        Raises:
          error.TestFail: If the timeout period does not match our spec.
        """
        # Record the boot time of firmware screen timeout.
        self.record_fw_boot_time('timeout_boot')
        got_timeout = (self.fw_time_record['timeout_boot'] -
                       self.fw_time_record['ctrl_d_boot'])
        logging.info('Estimated developer firmware timeout: %s', got_timeout)

        if (abs(got_timeout - self.delay.dev_screen_timeout) >
                self.TIMEOUT_MARGIN):
            raise error.TestFail(
                    'The developer firmware timeout does not match our spec: ' \
                    'expected %.2f +/- %.2f but got %.2f.' %
                    (self.delay.dev_screen_timeout, self.TIMEOUT_MARGIN,
                     got_timeout))


    def setup(self):
        super(firmware_DevScreenTimeout, self).setup()
        # This test is run on developer mode only.
        self.setup_dev_mode(dev_mode=True)
        self.setup_usbkey(usbkey=False)


    def run_once(self):
        # Always expected developer mode firmware A boot.
        self.register_faft_template({
             'state_checker': (self.checkers.crossystem_checker, {
                'devsw_boot': '1',
                'mainfw_act': 'A',
                'mainfw_type': 'developer',
             }),
        })
        self.register_faft_sequence((
            {   # Step 1, reboot and press Ctrl-D repeatedly
                'firmware_action': self.ctrl_d_repeatedly,
            },
            {   # Step 2, record the firmware boot time without waiting
                # firmware screen; on next reboot, do nothing and wait the
                # screen timeout.
                'userspace_action': (self.record_fw_boot_time, 'ctrl_d_boot'),
                'firmware_action': None,
            },
            {   # Step 3, check the firmware screen timeout matches our spec.
                'userspace_action': self.check_timeout_period,
            },
        ))
        self.run_faft_sequence()
