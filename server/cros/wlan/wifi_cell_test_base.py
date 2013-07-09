# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros.network import wifi_test_base
from autotest_lib.server.cros.wlan import wifi_test_context_manager

class WiFiCellTestBase(wifi_test_base.WiFiTestBase):
    """An abstract base class for autotests in WiFi cells.

    WiFiCell tests refer to participants in the test as client, router, and
    server.  The client is just the DUT and the router is a nearby AP which we
    configure in various ways to test the ability of the client to connect.
    There is a third entity called a server which is distinct from the autotest
    server.  In WiFiTests, the server is a host which the client can only talk
    to over the WiFi network.

    WiFiTests have a notion of the control network vs the WiFi network.  The
    control network refers to the network between the machine running the
    autotest server and the various machines involved in the test.  The WiFi
    network is the subnet(s) formed by WiFi routers between the server and the
    client.

    """

    def get_context(self, host, cmdline_args, additional_params):
        """Get the context object we should run this test in the context of.

        @param host Host object representing the DUT.
        @param cmdline_args dictionary of commandline args for the test.
        @param additional_params object passed in from the control file.
        @return WiFi test context object for use with the test.

        """
        return wifi_test_context_manager.WiFiTestContextManager(
                self.__class__.__name__,
                host,
                cmdline_args,
                self.debugdir)
