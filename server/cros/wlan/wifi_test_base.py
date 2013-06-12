# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import utils
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


    def parse_additional_arguments(self, commandline_args, additional_params):
        """Parse additional arguments for use in test.

        Subclasses should override this method do any other commandline parsing
        and setting grabbing that they need to do.  For test clarity, do not
        parse additional settings in the body of run_once.

        @param commandline_args dict of argument key, value pairs.
        @param additional_params object defined by test control file.

        """
        pass


    def warmup(self, host, raw_cmdline_args, additional_params=None):
        """
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

        self._wifi_context.setup()
        self.parse_additional_arguments(cmdline_args, additional_params)


    def cleanup(self):
        self._wifi_context.teardown()


    def get_context(self, host, cmdline_args, additional_params):
        """Get the context object we should run this test in the context of.

        @param host Host object representing the DUT.
        @param cmdline_args dictionary of commandline args for the test.
        @param additional_params object passed in from the control file.
        @return WiFi test context object for use with the test.

        """
        raise NotImplementedError('You must define your own get_context()!')
