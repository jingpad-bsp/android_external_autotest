# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

SHUTDOWN_STATEFUL_UMOUNT_FAIL = ('/mnt/stateful_partition/'
                                 'shutdown_stateful_umount_failure')

class platform_CleanShutdown(test.test):
    """Checks for the presence of an unclean shutdown file."""
    version = 1

    def run_once(self):
        if os.path.exists(SHUTDOWN_STATEFUL_UMOUNT_FAIL):
            raise error.TestFail(
                '{} exists!'.format(SHUTDOWN_STATEFUL_UMOUNT_FAIL))
