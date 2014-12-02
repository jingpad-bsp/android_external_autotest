# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import utils
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class firmware_FWtries(FirmwareTest):
    """Boot with firmware B until fwb_tries count down to 0

    Setup Steps:
    1. Check device in normal mode

    Test Steps:
    2. run crossystem fwb_tries=2
       [fwb_tries can be > 0 and <= 15. Value will be auto reset to 15 If
        the value is < 0 or > 15
    3. Reboot 1
    4. Reboot 2
    5. Reboot 3

    Verification Steps:
    1. After reboot 1, crossystem returns
    mainfw_act = B
    mainfw_type = normal
    fwb_tries = 1
    tried_fwb = 1

    2. After reboot 2, crossystem returns
    mainfw_act = B
    mainfw_type = normal
    fwb_tries = 0
    tried_fwb = 1

    3. After reboot 3, crossystem returns
    mainfw_act = A
    mainfw_type = normal
    fwb_tries = 0
    tried_fwb = 0
    """

    version = 1

    def initialize(self, host, cmdline_args):
        dict_args = utils.args_to_dict(cmdline_args)
        super(firmware_FWtries, self).initialize(host, cmdline_args)
        # Set device in normal mode
        self.setup_dev_mode(False)

    def dut_run_cmd(self, command):
        """Execute command on DUT.

        @param command: shell command to be executed on DUT.
        @returns command output.
        """
        logging.info('Execute %s', command)
        output = self.faft_client.system.run_shell_command_get_output(command)
        logging.info('Output %s', output)
        return output

    def run_once(self, host):
        self.check_state((self.checkers.crossystem_checker,
                          {'mainfw_act': 'A',
                           'mainfw_type': 'normal',
                           'fwb_tries': '0',
                           'tried_fwb': '0'}))
        command = 'crossystem fwb_tries=2'
        self.dut_run_cmd(command)
        self.check_state((self.checkers.crossystem_checker,
                          {'mainfw_act': 'A',
                           'mainfw_type': 'normal',
                           'fwb_tries': '2',
                           'tried_fwb': '0'}))

        host.reboot()
        self.check_state((self.checkers.crossystem_checker,
                          {'mainfw_act': 'B',
                           'mainfw_type': 'normal',
                           'fwb_tries': '1',
                           'tried_fwb': '1'}))
        host.reboot()
        self.check_state((self.checkers.crossystem_checker,
                          {'mainfw_act': 'B',
                           'mainfw_type': 'normal',
                           'fwb_tries': '0',
                           'tried_fwb': '1'}))

        host.reboot()
        self.check_state((self.checkers.crossystem_checker,
                         {'mainfw_act': 'A',
                          'mainfw_type': 'normal',
                          'fwb_tries': '0',
                          'tried_fwb': '0'}))
