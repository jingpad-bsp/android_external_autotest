# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'ups@chromium.org (Stephan Uphoff)'

import logging
import os
import utils

from autotest_lib.client.bin import utils, test
from autotest_lib.client.common_lib import error


class security_ChromiumOSLSM(test.test):
    """
    Verify Chromium OS Security Module behaves as expected.
    """
    version = 1

    def run_once(self):
        errors = 0
        test_directory= '/tmp/chromium_lsm_test_directory'
        os.mkdir(test_directory,0700)
        os.mkdir(test_directory + '/mount_point',0700)
        os.symlink('mount_point',test_directory + '/symlink')
        result = utils.system("mount -n -t tmpfs -o nodev,noexec,nosuid test " \
            + test_directory + "/symlink",ignore_status=True)
        # Mounting should fail as we used a mount path with a symbolic link.
        if result == 0:
            utils.system('umount ' + test_directory + '/symlink')
            logging.error('Failed symbolic link mount point test')
            errors += 1
        result = utils.system("mount -n -t tmpfs -o nodev,noexec,nosuid test " \
            + test_directory + "/mount_point",ignore_status=True)
        # Mounting should succeed (no symbolic link in mount path).
        if result != 0:
            logging.error('Failed regular mount')
            errors += 1
        else:
            utils.system('umount ' + test_directory + '/mount_point')

        utils.system('rm -rf ' + test_directory)
        # If self.error is not zero, there were errors.
        if errors > 0:
            raise error.TestFail('Failed %d tests' % errors)
