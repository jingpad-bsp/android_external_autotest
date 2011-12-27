# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import backchannel, network

from autotest_lib.client.cros.cellular import cellular, cell_tools
from autotest_lib.client.cros.cellular import emulator_config, labconfig

import logging, re, socket, string, time, urllib2

from autotest_lib.client.cros import flimflam_test_path
import flimflam, routing, mm

# Cellular smoke test and documentation for writing cell tests

class cellular_Smoke(test.test):
    version = 1

    # The autotest infrastructure calls run_once.  The control file
    # fetches the JSON lab config and passes it in as a python object

    def run_once(self, config, technology):
        # backchannel.Backchannel sets up an ethernet connection to the
        # DUT that has restrictive routes is outside of flimflam's
        # control.  This makes the tests resilient to flimflam restarts
        # and helps to ensure that the test is actually sending traffic on
        # the cellular link
        with backchannel.Backchannel():
            flim = flimflam.FlimFlam()

            # This shuts down other network devices on the host.  Again,
            # this is to ensure that test traffic goes over the modem
            with cell_tools.OtherDeviceShutdownContext('cellular', flim):
                bs, verifier = emulator_config.StartDefault(config, technology)

                network.ResetAllModems(flim)
                cell_tools.PrepareModemForTechnology('', technology)

                # TODO(rochberg) Need to figure out what isn't settling here.
                # Going to wait 'til after ResetAllModems changes land.
                time.sleep(10)

                (service, _) = cell_tools.ConnectToCellular(flim, verifier)
                cell_tools.CheckHttpConnectivity(config)

                cell_tools.DisconnectFromCellularService(bs, flim, service)
