# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time

from autotest_lib.client.common_lib import utils
from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_ConsecutiveBoot(FAFTSequence):
    """
    Servo based consecutive boot test.

    This test is intended to be run with many iterations to ensure that the DUT
    does boot into Chrome OS and then does power off later.

    The iteration should be specified by the parameter -a "faft_iterations=10"
    in run_remote_test.sh.
    """
    version = 1

    FULL_POWER_OFF_DELAY = 30


    def initialize(self, host, cmdline_args, use_pyauto=False, use_faft=True):
        # Parse arguments from command line
        dict_args = utils.args_to_dict(cmdline_args)
        self.faft_iterations = int(dict_args.get('faft_iterations', 1))
        super(firmware_ConsecutiveBoot, self).initialize(host, cmdline_args,
                                                         use_pyauto, use_faft)


    def setup(self, dev_mode=False):
        super(firmware_ConsecutiveBoot, self).setup()
        self.setup_dev_mode(dev_mode)


    def full_power_off_and_on(self):
        # Press power button to trigger Chrome OS normal shutdown process.
        self.servo.power_normal_press()
        time.sleep(self.FULL_POWER_OFF_DELAY)
        # Short press power button to boot DUT again.
        self.servo.power_short_press()


    def run_once(self, dev_mode=False, host=None):
        self.register_faft_sequence((
            {   # Step 1, expected boot fine, full power off DUT and on
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': 'developer' if dev_mode else 'normal',
                }),
                'reboot_action': self.full_power_off_and_on,
            },
            {   # Step 2, expected boot fine
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': 'developer' if dev_mode else 'normal',
                }),
            },
        ))
        for i in xrange(self.faft_iterations):
            logging.info('======== Running FAFT ITERATION %d/%s ========',
                         i+1, self.faft_iterations)
            self.run_faft_sequence()
