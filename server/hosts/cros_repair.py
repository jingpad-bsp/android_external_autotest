# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common
from autotest_lib.client.common_lib import hosts
from autotest_lib.server.hosts import ssh_verify


class CrosHostVerifier(hosts.Verifier):
    """
    Ask a CrOS host to perform its own verification.

    This class exists as a temporary legacy during refactoring to
    provide access to code that hasn't yet been rewritten to use the new
    repair and verify framework.
    """

    def verify(self, host):
        host.verify_software()
        host.verify_hardware()


    @property
    def tag(self):
        return 'cros'


    @property
    def description(self):
        return 'Miscellaneous CrOS host verification checks'


def create_repair_strategy():
    """Return a `RepairStrategy` for a `CrosHost`."""
    return hosts.RepairStrategy(((ssh_verify.SshVerifier, ()),
                                 (CrosHostVerifier, ('ssh',))))
