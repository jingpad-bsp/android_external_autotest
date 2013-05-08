# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.cros import dhcp_test_base

class network_DhcpNegotiationTimeout(dhcp_test_base.DhcpTestBase):
    """The DHCP Negotiation Timeout class.

    Sets up a virtual ethernet pair, stops the DHCP server on the pair,
    restarts shill, and waits for DHCP to timeout.

    After the timeout interval, checks if the same shill process is
    running. If not, report failure.

    """
    SHILL_DHCP_TIMEOUT_SECONDS = 30


    def test_body(self):
        """Test main loop."""
        self.server.stop()
        utils.run("restart shill")
        start_pid = int(utils.run("pgrep shill").stdout)

        time.sleep(self.SHILL_DHCP_TIMEOUT_SECONDS + 2)
        end_pid = int(utils.run("pgrep shill").stdout)
        if end_pid != start_pid:
            raise error.TestFail("shill restarted (probably crashed)")
