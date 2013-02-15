# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server import site_wifitest
from autotest_lib.server import site_host_route
from autotest_lib.server.cros import stress

class ONCTest(site_wifitest.WiFiTest):
    """ This class includes executing the ONC specific commands and is used
    in conjunction with WiFiTest for configuring the routers."""

    STATE_LIST  = {
        'STATE_LOGGED_IN': '/tmp/NETWORKONC_logged_in',
        'STATE_ONC_SET':'/tmp/NETWORKONC_onc_set',
        'STATE_EXIT':'/tmp/NETWORKONC_exit'
    }

    WAIT_FOR_CLIENT_TIMEOUT = 200

    def init_profile(self):
        # ONC type tests require chrome which seems to only like the default
        # profile.  For ONC tests, profile cleanup occurs when running
        # the client side test.
        pass


    def cleanup(self, params={}):
        self.client_logout()
        super(ONCTest, self).cleanup(params)


    def run_onc_client_test(self, params):
        if not params.get('test_type'):
          params['test_type'] = 'test_simple_set_user_onc'

        logging.info('Server: starting client test "%s"' % params['test_type'])
        self.client_at.run_test('network_ONC', **params)


    def set_user_onc(self, params):
        if not params.get('onc'):
            params['onc'] = ''

        params['test_type'] = 'test_simple_set_user_onc'

        # Start the thread that logs into chrome and sets the
        # device policy.
        self.client_test = stress.CountedStressor(
                                lambda: self.run_onc_client_test(params),
                                on_exit=lambda:self._client_logout())

        self.client_test.start(1)


    def _wait_for_client_state(self, state, timeout=WAIT_FOR_CLIENT_TIMEOUT):
        """ Waits till the client's state matches that of state.
        This is done via checking a series of state files the client
        writes to /tmp. """
        ending_time = time.time()+timeout
        while time.time() < ending_time:
            output = self.client.run('ls %s' % self.STATE_LIST[state],
                                     ignore_status=True)
            if output.exit_status == 0:
                break
            time.sleep(1)
        else:
            raise error.TestError('TIMEOUT waiting for ONC to be ready')


    def connect_wifi_onc(self, params):
        """ Connect to the configured AP. """
        # Wait for the ONC configuration to be ready before connecting.
        self._wait_for_client_state('STATE_ONC_SET')
        super(ONCTest, self).connect(params)


    def __add_host_route(self, host):
        """ Adding local and remote ip route. """
        # What is the local address we use to get to the test host?
        local_ip = site_host_route.LocalHostRoute(host.ip).route_info["src"]

        # How does the test host currently get to this local address?
        host_route = site_host_route.RemoteHostRoute(host, local_ip).route_info

        # Flatten the returned dict into a single string
        route_args = " ".join(" ".join(x) for x in host_route.iteritems())

        self.host_route_args[host.ip] = "%s %s" % (local_ip, route_args)
        host.run("ip route add %s" % self.host_route_args[host.ip])


    def connect_vpn_onc(self, params):
        """ Connect to the configured VPN. """
        # Wait for the ONC configuration to be ready before connecting.
        self._wait_for_client_state('STATE_ONC_SET')
        self.vpn_client_kill({}) # Must be first.  Relies on self.vpn_kind.
        # Starting up the VPN client may cause the DUT's routing table (esp.
        # the default route) to change.  Set up a host route backwards so
        # we don't lose our control connection in that event.
        self.__add_host_route(self.client)
        # Service is connectable after onc import
        result = self.client.run('%s/test/connect-service '
                                     ' l2tpipsec-psk ' %
                                     (self.client_cmd_flimflam_lib))


    def _client_logout(self):
        # To end the client thread, it relies on state exit to be
        # present.
        self.client.run('touch %s' % self.STATE_LIST['STATE_EXIT'],
                        ignore_status=True)


    def client_logout(self, params=None):
        if not hasattr(self, 'client_test'):
            return

        self._client_logout()
        self.client_test.join(self.WAIT_FOR_CLIENT_TIMEOUT)
        self.client_test.reraise()
