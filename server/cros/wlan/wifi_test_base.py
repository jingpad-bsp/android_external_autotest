# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server import test
from autotest_lib.server.cros import wifi_test_utils
from autotest_lib.server.cros.wlan import wifi_test_context_manager


class WiFiTestBase(test.test):
    """An abstract base class for WiFi autotests.

    WiFiTestBase handles many of the common tasks of WiFi autotests like
    setting up abstractions for clients, routers, and servers and implementing
    common test operations.

    WiFiTests refer to participants in the test as client, router, and server.
    The client is just the DUT and the router is a nearby AP which we configure
    in various ways to test the ability of the client to connect.  There is a
    third entity called a server which is distinct from the autotest server.
    In WiFiTests, the server is a host which the client can only talk to over
    the WiFi network.

    WiFiTests have a notion of the control network vs the WiFi network.  The
    control network refers to the network between the machine running the
    autotest server and the various machines involved in the test.  The WiFi
    network is the subnet(s) formed by WiFi routers between the server and the
    client.

    """

    @property
    def context(self):
        """@return WiFiTestContextManager for this test."""
        return self._wifi_context


    def assert_connect_wifi(self, wifi_params, expect_failure=False):
        """Connect to a WiFi network and check for success.

        Connect a DUT to a WiFi network and check that we connect successfully.

        @param wifi_params AssociationParameters describing network to connect.
        @param expect_failure bool True is connecting should fail.

        """
        logging.info('Connecting to %s.', wifi_params.ssid)
        serialized_assoc_result = self.context.client.shill.connect_wifi(
                wifi_params.serialize())
        assoc_result = xmlrpc_datatypes.AssociationResult(
                serialized=serialized_assoc_result)
        logging.info('Finished connection attempt to %s with times: '
                     'discovery=%.2f, association=%.2f, configuration=%.2f.',
                     wifi_params.ssid,
                     assoc_result.discovery_time,
                     assoc_result.association_time,
                     assoc_result.configuration_time)

        if assoc_result.success and expect_failure:
            raise error.TestFail(
                    'Expected connect to fail, but it was successful.')

        if not assoc_result.success and not expect_failure:
            raise error.TestFail('Expected connect to succeed, but it failed '
                                 'with reason: %s.' %
                                 assoc_result.failure_reason)

        logging.info('Connected successfully to %s.', wifi_params.ssid)


    def parse_additional_arguments(self, commandline_args, additional_params):
        """Parse additional arguments for use in test.

        Subclasses should override this method do any other commandline parsing
        and setting grabbing that they need to do.  For test clarity, do not
        parse additional settings in the body of run_once_impl.

        @param commandline_args dict of argument key, value pairs.
        @param additional_params object defined by test control file.

        """
        pass


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


    def run_once(self, host, raw_cmdline_args, additional_params=None):
        """Wrapper around bodies of test subclasses.

        This is the entry point from autotest proper.  We use it to set up
        an appropriate context for the test, populated with router, client,
        and server proxy objects.  We'll take care of the proper object
        cleanup after the actual test logic is finished.

        Use the additional_params argument to pass in custom test data from
        control file to reuse test logic.  This object will be passed down via
        parse_additional_arguments.

        @param host host object representing the client DUT.
        @param raw_cmdline_args raw input from autotest.
        @param additional_params object passed in from control file.

        """
        cmdline_args = utils.args_to_dict(raw_cmdline_args)
        logging.info('Running wifi test with commandline arguments: %r',
                     cmdline_args)

        with wifi_test_context_manager.WiFiTestContextManager(
                self.__class__.__name__,
                host,
                cmdline_args,
                self.debugdir) as context:
            self._wifi_context = context
            self.parse_additional_arguments(cmdline_args, additional_params)
            logging.debug('Calling into actual test logic.')
            self.run_once_impl()
            logging.debug('Actual test logic completed successfully.')


    def run_once_impl(self):
        """Body of the test.  Override this in your subclass."""
        raise NotImplementedError('You must define your own run_once_impl()!')
