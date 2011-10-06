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

class cellular_Smoke(test.test):
  version = 1

  def run_once(self, config):
    with backchannel.Backchannel():
      flim = flimflam.FlimFlam()
      with cell_tools.OtherDeviceShutdownContext('cellular', flim):

        bs = emulator_config.ConfigureBaseStations(config)[0]
        verifier = bs.GetAirStateVerifier()

        bs.SetTechnology(cellular.Technology.WCDMA)
        bs.SetPower(-50)
        bs.Start()

        network.ResetAllModems(flim)

        cell_tools.ConnectToCellNetwork(flim)
        verifier.AssertDataStatusIn([cellular.UeStatus.ACTIVE])
