# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.server import hosts
from autotest_lib.server import site_linux_bridge_router
from autotest_lib.server import site_linux_cros_router
from autotest_lib.server import site_linux_server
from autotest_lib.server.cros import wifi_test_utils
from autotest_lib.server.cros.wlan import wifi_client


class WiFiTestContextManager(object):
    """A context manager for state used in WiFi autotests.

    Some of the building blocks we use in WiFi tests need to be cleaned up
    after use.  For instance, we start an XMLRPC server on the client
    which should be shut down so that the next test can start its instance.
    It is convenient to manage this setup and teardown through a context
    manager rather than building it into the test class logic.

    """

    CMDLINE_CLIENT_PACKET_CAPTURES = 'client_capture'
    CMDLINE_ROUTER_PACKET_CAPTURES = 'router_capture'
    CMDLINE_ROUTER_ADDR = 'router_addr'
    CMDLINE_ROUTER_PORT = 'router_port'
    CMDLINE_SERVER_ADDR = 'server_addr'


    @property
    def server_address(self):
        """@return string address of WiFi server host in test."""
        hostname = self.client.host.hostname
        if utils.host_is_in_lab_zone(hostname):
            # Lab naming convention in: go/chromeos-lab-hostname-convention
            return wifi_test_utils.get_server_addr_in_lab(hostname)

        elif self.CMDLINE_SERVER_ADDR in self._cmdline_args:
            return self._cmdline_args[self.CMDLINE_SERVER_ADDR]

        raise error.TestError('Test not running in lab zone and no '
                              'server address given')


    @property
    def router_address(self):
        """@return string address of WiFi router host in test."""
        hostname = self.client.host.hostname
        if utils.host_is_in_lab_zone(hostname):
            # Lab naming convention in: go/chromeos-lab-hostname-convention
            return wifi_test_utils.get_router_addr_in_lab(hostname)

        elif self.CMDLINE_ROUTER_ADDR in self._cmdline_args:
            return self._cmdline_args[self.CMDLINE_ROUTER_ADDR]

        raise error.TestError('Test not running in lab zone and no '
                              'router address given')


    def __init__(self, test_name, host, cmdline_args, debug_dir):
        """Construct a WiFiTestContextManager.

        Optionally can pull addresses of the server address, router address,
        or router port from cmdline_args.

        @param test_name string descriptive name for this test.
        @param host host object representing the DUT.
        @param cmdline_args dict of key, value settings from command line.

        """
        super(WiFiTestContextManager, self).__init__()
        self._test_name = test_name
        self._cmdline_args = cmdline_args.copy()
        self._client_proxy = wifi_client.WiFiClient(host, debug_dir)
        self._router = None
        self._server = None
        self._enable_client_packet_captures = False
        self._enable_router_packet_captures = False


    def __enter__(self):
        self.setup()
        return self


    def __exit__(self, exc_type, exc_value, traceback):
        self.teardown()


    @property
    def client(self):
        """@return WiFiClient object abstracting the DUT."""
        return self._client_proxy


    @property
    def router(self):
        """@return router object (e.g. a LinuxCrosRouter)."""
        return self._router


    @property
    def server(self):
        """@return server object representing the server in the test."""
        return self._server


    def get_wifi_addr(self, ap_num=0):
        """Return an IPv4 address pingable by the client on the WiFi subnet.

        @param ap_num int number of AP.  Only used in stumpy cells.
        @return string IPv4 address.

        """
        if self.router.has_local_server():
            return self.router.local_server_address(ap_num)
        return self.server.wifi_ip


    def configure(self, configuration_parameters, multi_interface=None,
                  is_ibss=None):
        """Configure a router with the given parameters.

        Configures an AP according to the specified parameters and
        enables whatever packet captures are appropriate.  Will deconfigure
        existing APs unless |multi_interface| is specified.

        @param configuration_parameters HostapConfig object.
        @param multi_interface True iff having multiple configured interfaces
                is expected for this configure call.
        @param is_ibss True iff this is an IBSS endpoint.

        """
        if is_ibss:
            if multi_interface:
                raise error.TestFail('IBSS mode does not support multiple '
                                     'interfaces.')

            self.router.ibss_configure(configuration_parameters)
        else:
            self.router.hostap_configure(configuration_parameters,
                                         multi_interface=multi_interface)
        if self._enable_client_packet_captures:
            self.client.start_capture()
        if self._enable_router_packet_captures:
            self.router.start_capture(
                    configuration_parameters.frequency,
                    ht_type=configuration_parameters.ht_packet_capture_mode)


    def setup(self):
        """Construct the state used in a WiFi test."""
        # Build up our router we're going to use in the test.  This involves
        # figuring out what kind of test setup we're using.
        router_port = int(self._cmdline_args.get(self.CMDLINE_ROUTER_PORT, 22))
        logging.info('Connecting to router at %s:%d',
                     self.router_address, router_port)
        router_host = hosts.SSHHost(self.router_address, port=router_port)
        # TODO(wiley) Simplify the router and make the parameters explicit.
        router_params = {}
        default_ssid = wifi_test_utils.get_default_ssid(self._test_name,
                                                        self.router_address,
                                                        router_host)
        logging.info('Default router SSID is %s.', default_ssid)
        if site_linux_cros_router.isLinuxCrosRouter(router_host):
            self._router = site_linux_cros_router.LinuxCrosRouter(
                    router_host, router_params, default_ssid)
        else:
            self._router = site_linux_bridge_router.LinuxBridgeRouter(
                    router_host, router_params, default_ssid)
        # If we're testing WiFi, we're probably going to need one of these.
        self._router.create_wifi_device()
        # The '_server' is a machine which hosts network
        # services, such as OpenVPN or StrongSwan.
        server_host = hosts.SSHHost(self.server_address, port=22)
        self._server = site_linux_server.LinuxServer(server_host, {})
        # Set up a test profile on a clean stack.
        self.client.shill.clean_profiles()
        # This extra remove takes care of a case where we popped the test
        # profile in a previous test, but crashed before we removed it.
        self.client.shill.remove_profile('test')
        self.client.shill.create_profile('test')
        self.client.shill.push_profile('test')
        if self.CMDLINE_CLIENT_PACKET_CAPTURES in self._cmdline_args:
            self._enable_client_packet_captures = True
        if self.CMDLINE_ROUTER_PACKET_CAPTURES in self._cmdline_args:
            self._enable_router_packet_captures = True
        wifi_test_utils.sync_host_times((self.client.host,
                                         self.server.host,
                                         self.router.host))


    def teardown(self):
        """Teardown the state used in a WiFi test."""
        logging.debug('Tearing down the test context.')
        self.client.shill.clean_profiles()
        self.client.close()
        self._router.destroy()
