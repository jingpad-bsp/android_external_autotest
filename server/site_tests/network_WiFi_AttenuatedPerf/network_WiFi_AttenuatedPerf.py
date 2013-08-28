# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server.cros.network import netperf_runner
from autotest_lib.server.cros.network import netperf_wifi_perf_logger
from autotest_lib.server.cros.network import netperf_session
from autotest_lib.server.cros.network import rvr_test_base


class network_WiFi_AttenuatedPerf(rvr_test_base.RvRTestBase):
    """Test maximal achievable bandwidth while varying attenuation.

    Performs a performance test for a specified router configuration as
    signal attentuation increases.

    """

    version = 1

    NETPERF_CONFIGS = [
            netperf_runner.NetperfConfig(
                       netperf_runner.NetperfConfig.TEST_TYPE_TCP_STREAM),
            netperf_runner.NetperfConfig(
                       netperf_runner.NetperfConfig.TEST_TYPE_TCP_MAERTS),
            netperf_runner.NetperfConfig(
                       netperf_runner.NetperfConfig.TEST_TYPE_UDP_STREAM),
            netperf_runner.NetperfConfig(
                       netperf_runner.NetperfConfig.TEST_TYPE_UDP_MAERTS),
    ]

    STARTING_ATTENUATION = 60
    ATTENUATION_STEP = 4
    FINAL_ATTENUATION = 100


    def parse_additional_arguments(self, commandline_args, additional_params):
        """Hook into super class to take control files parameters.

        @param commandline_args dict of parsed parameters from the autotest.
        @param additional_params list of dicts describing router configs.

        """
        self._ap_config = additional_params


    def run_once(self):
        start_time = time.time()
        keyval_logger = netperf_wifi_perf_logger.NetperfWiFiPerfLogger(
                self._ap_config, self.context.client, self.write_perf_keyval)
        # Set up the router and associate the client with it.
        self.context.configure(self._ap_config)
        assoc_params = xmlrpc_datatypes.AssociationParameters(
                ssid=self.context.router.get_ssid(),
                security_config=self._ap_config.security_config)
        self.context.assert_connect_wifi(assoc_params)
        # Conduct the performance tests.  Ignore failures, since
        # at high attenuations, sometimes the control connection
        # is unable to terminate the test properly.
        session = netperf_session.NetperfSession(self.context.client,
                                                 self.context.server,
                                                 ignore_failures=True)
        session.warmup_stations()
        for atten in range(self.STARTING_ATTENUATION,
                           self.FINAL_ATTENUATION + 1,
                           self.ATTENUATION_STEP):
            self.context.attenuator.set_total_attenuation(atten)
            logging.info('RvR test: current attenuation = %d dB', atten)
            atten_tag = 'atten%03d' % atten
            for config in self.NETPERF_CONFIGS:
                test_tag = '_'.join([atten_tag, config.tag])
                result = session.run(config)
                if result is None:
                    logging.warning('Unable to take measurement for %s',
                                    test_tag)
                    continue

                keyval_logger.record_keyvals_for_result(
                        result, descriptive_tag=test_tag)
            keyval_logger.record_signal_keyval(descriptive_tag=atten_tag)
        # Clean up router and client state.
        self.context.client.shill.disconnect(assoc_params.ssid)
        self.context.router.deconfig()
        end_time = time.time()
        logging.info('Running time %0.1f seconds.', end_time - start_time)
