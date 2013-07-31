# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server.cros.network import netperf_session
from autotest_lib.server.cros.network import wifi_cell_test_base


class network_WiFi_Netperf(wifi_cell_test_base.WiFiCellTestBase):
    """Test that we can aggregate frames to achieve "high" throughput."""
    version = 1


    def parse_additional_arguments(self, commandline_args, additional_params):
        """Hook into super class to take control files parameters.

        @param commandline_args dict of parsed parameters from the autotest.
        @param additional_params list of dicts describing router configs.

        """
        self._configurations = additional_params


    def run_once(self):
        """Test body."""
        have_failures = False
        for configuration in self._configurations:
            hostap_config, netperf_config, netperf_assertions = configuration
            self.context.configure(hostap_config)
            assoc_params = xmlrpc_datatypes.AssociationParameters(
                    ssid=self.context.router.get_ssid(),
                    security_config=hostap_config.security_config)
            self.context.assert_connect_wifi(assoc_params)
            session = netperf_session.NetperfSession(self.context.client,
                                                     self.context.server)
            session.warmup_stations()
            netperf_result = session.run(netperf_config)
            logging.debug('Checking assertions %r', netperf_assertions)
            if not netperf_assertions.passes(netperf_result):
                logging.error('===========================================')
                logging.error('Netperf failed!')
                logging.error(hostap_config)
                logging.error(netperf_config)
                logging.error(netperf_result)
                logging.error(netperf_assertions)
                have_failures = True
            self.context.client.shill.disconnect(assoc_params.ssid)
            self.context.router.deconfig()
        if have_failures:
            raise error.TestFail('One or more netperf runs failed.')

