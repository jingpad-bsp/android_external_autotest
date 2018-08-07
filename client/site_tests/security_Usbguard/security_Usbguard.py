# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import logging

from autotest_lib.client.bin import test, utils


class security_Usbguard(test.test):
    """Tests the usbguard basic functionality and seccomp policy.
    """

    version = 1
    SECCOMP_POLICY_FILE = '/opt/google/usbguard/usbguard-daemon-seccomp.policy'

    def run_once(self):
        """Runs the security_Usbguard test.
        """
        logging.info(utils.run(
            '/sbin/minijail0 -S %s /usr/bin/usbguard generate-policy' %
            (self.SECCOMP_POLICY_FILE,)))
