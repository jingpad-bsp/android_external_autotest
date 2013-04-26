# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import utils
from autotest_lib.server import hosts
from autotest_lib.server import site_attenuator
from autotest_lib.server.cros import wifi_test_utils
from autotest_lib.server.cros.wlan import wifi_test_context_manager


class RvRTestContextManager(wifi_test_context_manager.WiFiTestContextManager):
    """A context manager for state used in WiFi autotests.

    Some of the building blocks we use in WiFi tests need to be cleaned up
    after use.  For instance, we start an XMLRPC server on the client
    which should be shut down so that the next test can start its instance.
    It is convenient to manage this setup and teardown through a context
    manager rather than building it into the test class logic.

    """

    CMDLINE_ATTEN_ADDR = 'atten_addr'


    def __init__(self, test_name, host, cmdline_args, debug_dir):
        """Construct a WiFiTestContextManager.

        Optionally can pull addresses of the server address, router address,
        or router port from cmdline_args.

        @param test_name string descriptive name for this test.
        @param host host object representing the DUT.
        @param cmdline_args dict of key, value settings from command line.
        @param debug_dir string of directory path to save packet capture files.

        """
        super(RvRTestContextManager, self).__init__(
                test_name, host, cmdline_args, debug_dir)
        self._attenuator = None


    @property
    def attenuator(self):
        """@return attenuator object (e.g. a BeagleBone)."""
        return self._attenuator


    @property
    def attenuator_address(self):
        """@return string address of WiFi attenuator host in test."""
        hostname = self.client.host.hostname
        if utils.host_is_in_lab_zone(hostname):
            return wifi_test_utils.get_attenuator_addr_in_lab(hostname)

        elif self.CMDLINE_ATTEN_ADDR in self._cmdline_args:
            return self._cmdline_args[self.CMDLINE_ATTEN_ADDR]

        raise error.TestError('Test not running in lab zone and no '
                              'attenuator address given')


    def _set_up_attenuator(self):
        """Creates and initializes variable attenuators."""
        logging.info('Creating attenuator object ...')
        attenuator_host = hosts.SSHHost(self.attenuator_address, port=22)
        self._attenuator = site_attenuator.Attenuator(attenuator_host)
        for port in [0, 1]:  # We only use ports 0 and 1.
            self._attenuator.init_atten_port(port)
        logging.info('Attenuator ports initialized.')


    def setup(self):
        """Construct the state used in a WiFi test."""
        super(RvRTestContextManager, self).setup()
        self._set_up_attenuator()

