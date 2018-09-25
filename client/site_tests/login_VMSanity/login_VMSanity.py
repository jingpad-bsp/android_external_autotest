# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, vm_sanity


class login_VMSanity(test.test):
    """Run vm_sanity."""
    version = 1

    def run_once(self):
        # Don't run Tast tests in this test, as there's already plenty of other
        # infrastructure for running them in the lab: http://go/tast-infra
        vm_sanity.VMSanity(run_tast=False).Run()
