# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(hungte) remove this test after we've made sure no one is using it
# anymore.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class hardware_DeveloperRecovery(test.test):
    version = 1

    def run_once(self):
        # raise error.TestFail('always fail')
        pass
