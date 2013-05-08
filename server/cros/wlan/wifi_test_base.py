# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server import test


class WiFiTestBase(test.test):
    """An abstract base class for WiFi autotests.

    WiFiTestBase calls into a concrete test base class after setting up the
    context for the test.  The context should contain the set of clients,
    routers, and WiFiTest servers required by the test proper.  WiFiTestBase
    also provides some simple functionality, such as logic to check that a
    client can connect to a specified WiFi network.

    """

    @property
    def context(self):
        """@return the WiFi context for this test."""
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


    def run_once(self, host, raw_cmdline_args, additional_params=None):
        """Wrapper around bodies of test subclasses.

        This is the entry point from autotest proper.  We use it to set up
        an appropriate context for the test, call into the actual test logic,
        and clean up the final state of the test.

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
        self._wifi_context = self.get_context(host, cmdline_args,
                                              additional_params)
        with self.context:
            self.parse_additional_arguments(cmdline_args, additional_params)
            logging.debug('Calling into actual test logic.')
            self.run_once_impl()
            logging.debug('Actual test logic completed successfully.')


    def run_once_impl(self):
        """Body of the test.  Override this in your subclass."""
        raise NotImplementedError('You must define your own run_once_impl()!')


    def get_context(self, host, cmdline_args, additional_params):
        """Get the context object we should run this test in the context of.

        @param host Host object representing the DUT.
        @param cmdline_args dictionary of commandline args for the test.
        @param additional_params object passed in from the control file.
        @return WiFi test context object for use with the test.

        """
        raise NotImplementedError('You must define your own get_context()!')
