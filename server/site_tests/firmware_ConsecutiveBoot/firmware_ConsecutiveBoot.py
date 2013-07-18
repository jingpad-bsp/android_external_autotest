# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import utils
from autotest_lib.server.cros.faft_classes import FAFTSequence


class firmware_ConsecutiveBoot(FAFTSequence):
    """
    Servo based consecutive boot test.

    This test is intended to be run with many iterations to ensure that the DUT
    does boot into Chrome OS and then does power off later.

    The iteration should be specified by the parameter -a "faft_iterations=10"
    in run_remote_test.sh.
    """
    version = 1


    def initialize(self, host, cmdline_args):
        # Parse arguments from command line
        dict_args = utils.args_to_dict(cmdline_args)
        self.faft_iterations = int(dict_args.get('faft_iterations', 1))
        super(firmware_ConsecutiveBoot, self).initialize(host, cmdline_args)


    def setup(self, dev_mode=False):
        super(firmware_ConsecutiveBoot, self).setup()
        self.setup_dev_mode(dev_mode)
        self.setup_usbkey(usbkey=False)


    def run_once(self, dev_mode=False):
        self.register_faft_sequence((
            {   # Step 1, expected boot fine, full power off DUT and on
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_type': 'developer' if dev_mode else 'normal',
                }),
                'reboot_action': self.full_power_off_and_on,
            },
            {   # Step 2, expected boot fine
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_type': 'developer' if dev_mode else 'normal',
                }),
            },
        ))
        for i in xrange(self.faft_iterations):
            logging.info('======== Running FAFT ITERATION %d/%s ========',
                         i+1, self.faft_iterations)
            self.run_faft_sequence()
