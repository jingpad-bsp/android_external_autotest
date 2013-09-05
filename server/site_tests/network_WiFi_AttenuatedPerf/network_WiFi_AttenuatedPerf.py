# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import logging
import os.path
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

    CMDLINE_SERIES_NOTE = 'series_note'

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

    TSV_OUTPUT_DIR = 'tsvs'

    DataPoint = collections.namedtuple('DataPoint',
                                       ['attenuation', 'throughput',
                                        'variance', 'signal', 'test_type'])


    def parse_additional_arguments(self, commandline_args, additional_params):
        """Hook into super class to take control files parameters.

        @param commandline_args dict of parsed parameters from the autotest.
        @param additional_params list of dicts describing router configs.

        """
        self._ap_config = additional_params
        self.series_note = None
        if self.CMDLINE_SERIES_NOTE in commandline_args:
            self.series_note = commandline_args[self.CMDLINE_SERIES_NOTE]


    def run_once(self):
        start_time = time.time()
        throughput_data = []
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
                if result.throughput is not None:
                    throughput_data.append(self.DataPoint(
                            atten,
                            result.throughput,
                            result.throughput_dev,
                            self.context.client.wifi_signal_level,
                            config.tag))
            keyval_logger.record_signal_keyval(descriptive_tag=atten_tag)
        # Clean up router and client state.
        self.context.client.shill.disconnect(assoc_params.ssid)
        self.context.router.deconfig()
        end_time = time.time()
        logging.info('Running time %0.1f seconds.', end_time - start_time)
        self.write_throughput_tsv_files(throughput_data)


    def write_throughput_tsv_files(self, throughput_data):
        """Write out .tsv files with plotable data from |throughput_data|.

        Each .tsv file starts with a label for the series that can be
        customized with a short note passed in from the command line.
        It then has column headers and fields separated by tabs.  This format
        is easy to parse and also works well with spreadsheet programs for
        custom report generation.

        @param throughput_data a list of Datapoint namedtuples gathered from
                tests.

        """
        logging.info('Writing .tsv files.')
        os.mkdir(os.path.join(self.resultsdir, self.TSV_OUTPUT_DIR))
        series_label_parts = [self.context.client.board,
                              'ch%03d' % self._ap_config.channel]
        if self.series_note:
            series_label_parts.insert(1, '(%s)' % self.series_note)
        header_parts = ['Attenuation', 'Throughput(Mbps)', 'StdDev(Mbps)',
                        'Client Reported Signal']
        mode = self._ap_config.printable_mode
        mode = mode.replace('+', 'p').replace('-', 'm').lower()
        result_file_prefix = '%s_ch%03d' % (mode, self._ap_config.channel)
        for test_type in set([data.test_type for data in throughput_data]):
            result_file = os.path.join(
                    self.resultsdir, self.TSV_OUTPUT_DIR,
                    '%s_%s.tsv' % (result_file_prefix, test_type))
            lines = [' '.join(series_label_parts),
                     '\t'.join(header_parts)]
            for result in sorted([datum for datum in throughput_data
                                  if datum.test_type == test_type]):
                lines.append('\t'.join(map(str, result[0:4])))
            with open(result_file, 'w') as f:
                f.writelines(['%s\n' % line for line in lines])
