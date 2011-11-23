# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging, time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import backchannel, iperf, network

from autotest_lib.client.cros.cellular import cellular, cell_tools
from autotest_lib.client.cros.cellular import emulator_config, labconfig

from autotest_lib.client.cros import flimflam_test_path
import flimflam


class cellular_Throughput(test.test):
    version = 1

    def run_once(self, config):
        with backchannel.Backchannel():
            flim = flimflam.FlimFlam()
            with cell_tools.OtherDeviceShutdownContext('cellular', flim):
                bs, verifier = emulator_config.GetDefaultBasestation(
                    config, cellular.Technology.WCDMA)
                network.ResetAllModems(flim)
                # TODO(rochberg): Figure out whether it's just Gobi 2k
                # that requires this or all modems
                time.sleep(10)

                (service, _) = cell_tools.ConnectToCellular(flim, verifier)

                cell_tools.CheckHttpConnectivity(config)

                # TODO(rochberg): Factor this and the counts stuff out
                # so that individual tests don't have to care.
                bs.LogStats()
                bs.ResetDataCounters()

                # The control file has started iperf at this address
                perftarget = config['perfserver']['rf_address']
                (client, perf) = iperf.BuildClientCommand(
                    perftarget,
                    {'tradeoff': True,})

                with network.IpTablesContext(perftarget):
                    iperf_output = utils.system_output(client,
                                                       retain_output=True)

                # TODO(rochberg):  Can/should we these values into the
                # write_perf_keyval dictionary?  Now we just log them.
                bs.GetDataCounters()

                # Add in conditions from BuildClientCommand
                perf.update(iperf.ParseIperfOutput(iperf_output))
                cell_tools.DisconnectFromCellularService(bs, flim, service)
                self.write_perf_keyval(perf)
