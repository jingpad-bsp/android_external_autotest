# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros.wlan import rvr_test_context_manager
from autotest_lib.server.cros.network import wifi_test_base


class RvRTestBase(wifi_test_base.WiFiTestBase):
    """An abstract base class for WiFi RvR autotests."""


    def get_context(self, host, cmdline_args, additional_params):
        """Get the context object we should run this test in the context of.

        @param host Host object representing the DUT.
        @param cmdline_args dictionary of commandline args for the test.
        @param additional_params object passed in from the control file.
        @return WiFi test context object for use with the test.

        """
        return rvr_test_context_manager.RvRTestContextManager(
                self.__class__.__name__,
                host,
                cmdline_args,
                self.debugdir)
