# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A test which verifies the camera function with HAL3 interface."""

import os, logging
from autotest_lib.client.bin import test, utils
from autotest_lib.client.cros import service_stopper

class camera_HAL3(test.test):
    """
    This test is a wrapper of the test binary arc_camera3_test.
    """

    version = 1
    test_binary = 'arc_camera3_test'
    dep = 'camera_hal3'
    adapter_service = 'camera-halv3-adapter'
    timeout = 600

    def setup(self):
        """
        Run common setup steps.
        """
        self.dep_dir = os.path.join(self.autodir, 'deps', self.dep)
        self.job.setup_dep([self.dep])
        logging.debug('mydep is at %s' % self.dep_dir)

    def run_once(self):
        """
        Entry point of this test.
        """
        self.job.install_pkg(self.dep, 'dep', self.dep_dir)

        with service_stopper.ServiceStopper([self.adapter_service]):
            binary_path = os.path.join(self.dep_dir, 'bin', self.test_binary)
            utils.system(binary_path, timeout=self.timeout)
