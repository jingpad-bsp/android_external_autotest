# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros import wifi_test_utils
from autotest_lib.server.cros.wlan import wifi_test_base
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

    def assert_ping_from_dut(self, additional_ping_params=None, ap_num=None):
        """Ping a host on the WiFi network from the DUT.

        Ping a host reachable on the WiFi network from the DUT, and
        check that the ping is successful.  The host we ping depends
        on the test setup, sometimes that host may be the server and
        sometimes it will be the router itself.  Ping-ability may be
        used to confirm that a WiFi network is operating correctly.

        @param additional_ping_params dict of optional parameters to ping.
        @param ap_num int which AP to ping if more than one is configured.

        """
        logging.info('Pinging from DUT.')
        if ap_num is None:
            ap_num = 0
        if additional_ping_params is None:
            additional_ping_params = {}
        ping_ip = self.context.get_wifi_addr(ap_num=ap_num)
        result = self.context.client.ping(ping_ip, additional_ping_params)
        stats = wifi_test_utils.parse_ping_output(result)
        # These are percentages.
        if float(stats['loss']) > 20:
            raise error.TestFail('Client lost ping packets: %r.', stats)
        logging.info('Ping successful.')


    def assert_ping_from_server(self, additional_ping_params=None):
        """Ping the DUT across the WiFi network from the server.

        Check that the ping is mostly successful and fail the test if it
        is not.

        @param additional_ping_params dict of optional parameters to ping.

        """
        logging.info('Pinging from server.')
        if additional_ping_params is None:
            additional_ping_params = {}
        ping_count = 10
        stats = self.context.server.ping(self.context.client.wifi_ip,
                                         ping_count, additional_ping_params)
        # These are percentages.
        if float(stats['loss']) > 20:
            raise error.TestFail('Server lost ping packets: %r.', stats)
        logging.info('Ping successful.')


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
