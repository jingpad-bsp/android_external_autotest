# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import utils
from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_CgptStress(FAFTSequence):
    """
    Servo based, iterative cgpt test. One iteration of test modifies CGPT to
    switch to boot kernel B and then switch back to kernel A again.
    """
    version = 1


    def initialize(self, host, cmdline_args, use_pyauto=False, use_faft=True):
        # Parse arguments from command line
        dict_args = utils.args_to_dict(cmdline_args)
        self.faft_iterations = int(dict_args.get('faft_iterations', 1))
        super(firmware_CgptStress, self).initialize(host, cmdline_args,
                                                       use_pyauto, use_faft)


    def setup(self, dev_mode=False):
        super(firmware_CgptStress, self).setup()
        self.setup_dev_mode(dev_mode)
        self.setup_usbkey(usbkey=False)
        self.setup_kernel('a')


    def cleanup(self):
        self.ensure_kernel_boot('a')
        super(firmware_CgptStress, self).cleanup()


    def run_once(self):
        self.register_faft_sequence((
            {   # Step 1, expected kernel A boot and prioritize kernel B
                'state_checker': (self.checkers.root_part_checker, 'a'),
                'userspace_action': (self.reset_and_prioritize_kernel, 'b'),
                'reboot_action': self.warm_reboot,
            },
            {   # Step 2, expected kernel B boot and prioritize kernel A
                'state_checker': (self.checkers.root_part_checker, 'b'),
                'userspace_action': (self.reset_and_prioritize_kernel, 'a'),
                'reboot_action': self.warm_reboot,
            },
            {   # Step 3, expected kernel A boot, done
                'state_checker': (self.checkers.root_part_checker, 'a'),
            },
        ))
        for i in xrange(self.faft_iterations):
            logging.info('======== Running FAFT ITERATION %d/%s ========',
                         i+1, self.faft_iterations)
            self.run_faft_sequence()
