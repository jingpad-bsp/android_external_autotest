# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib.cros.wlan import xmlrpc_datatypes
from autotest_lib.server.cros.wlan import rvr_test_base
from autotest_lib.server.cros.wlan import iperf_runner


class network_WiFi_RateRange(rvr_test_base.RvRTestBase):
    """Measures rate vs. range performance data on various configurations.

    WiFi_RateRange is a suite of 3-machine tests.

    1. Device under test (dut)
    2. WLAN access point (router, also doubles as iperf end point)
    3. Variable attenuator (attenuator)
    """

    version = 1


    def parse_additional_arguments(self, raw_cmdline_args, additional_params):
        """Hook into super class to take control files parameters.

        This method is invoked before run_once_impl() below.

        @param raw_cmdline_args dict of parsed parameters from the autotest.
        @param additional_params list of dicts describing router configs.
        @raises TestError: if ap_config is not found in additional_params.
        """
        ap_config, iperf_config = additional_params
        if not ap_config:
            raise error.TestError('Missing AP configuration.')
        self._ap_config = ap_config

        if not iperf_config:
            raise error.TestError('Missing Iperf configuration.')
        self._iperf_config = iperf_config

        self.write_attr_keyval({'ap_config': str(ap_config),
                                'iperf_config': str(iperf_config)})


    def run_once_impl(self):
        """Sets up a router, connects to it, pings it, and repeats."""
        iperf_helper = iperf_runner.IperfRunner(
                dut=self.context.client,
                ap=self.context.server)

        self.context.configure(self._ap_config)
        assoc_params = xmlrpc_datatypes.AssociationParameters()
        assoc_params.ssid = self.context.router.get_ssid()
        self.assert_connect_wifi(assoc_params)

        # FIXME(tgao): do not hard code
        atten_step = 2
        start_atten = 60
        end_atten = 101
        for atten in range(start_atten, end_atten+1, atten_step):
            self.context.attenuator.set_total_attenuation(atten)
            logging.info('RvR test: current attenuation = %d dB', atten)
            perf_data = iperf_helper.run(self._iperf_config)
            perf_data['total_atten_db'] = atten
            self.write_perf_keyval(perf_data)

        self.context.client.shill.disconnect(assoc_params.ssid)
        self.context.router.deconfig()
