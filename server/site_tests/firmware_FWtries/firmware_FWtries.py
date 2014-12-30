# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import utils
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class firmware_FWtries(FirmwareTest):
    """
    Boot with firmware B until fwb_tries/fw_try_count counts down to
    0.  vboot1 only needs to set fwb_tries in order to boot into FWB,
    but vboot2 needs to set two fields: fw_try_next and fw_try_count
    in order to do so.

    Setup Steps:
    1. Check device in normal mode

    Test Steps:
    2. Set # of tries to 2 (through try_fwb)
      a.  For vboot1:
        set fwb_tries=2
        [fwb_tries can be > 0 and <= 15. Value will be auto reset to 15 If
        the value is < 0 or > 15
      b.  For vboot2:
        set fw_try_next=B fw_try_count=2
    3. Reboot 1
    4. Reboot 2
    5. Reboot 3

    Verification Steps:
    1. After reboot 1, fw_tries_checker checks that
    mainfw_act = B
    fwb_tries/fw_try_count = 1

    2. After reboot 2, fw_tries_checker checks that
    mainfw_act = B
    fwb_tries/fw_try_count = 0

    3. After reboot 3, fw_tries_checker
    mainfw_act = A
    fwb_tries/fw_try_count = 0
    """

    version = 1

    def initialize(self, host, cmdline_args):
        dict_args = utils.args_to_dict(cmdline_args)
        super(firmware_FWtries, self).initialize(host, cmdline_args)
        # Set device in normal mode
        self.setup_dev_mode(False)

    def run_once(self, host):
        self.check_state((self.checkers.fw_tries_checker, ('A', True, 0)))

        self.try_fwb(2);

        self.check_state((self.checkers.fw_tries_checker, ('A', True, 2)))
        host.reboot()
        self.check_state((self.checkers.fw_tries_checker, ('B', True, 1)))
        host.reboot()
        self.check_state((self.checkers.fw_tries_checker, ('B', True, 0)))
        host.reboot()
        self.check_state((self.checkers.fw_tries_checker, ('A', True, 0)))
