# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import StringIO

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.cros.rf import agilent_scpi

FREQUENCIES = [
  836.5e6,
  1732.5e6,
  2132.5e6
]

class factory_Antenna(test.test):
    version = 1

    def run_once(self, ena_host):
        ena = agilent_scpi.ENASCPI(ena_host)
        # Get traces from 700Mhz to 2.2GHz
        ena.SetLinearSweep(min_freq=700e6, max_freq=2200e6)
        ret = ena.GetTraces(parameters=['S11', 'S12', 'S22'])
        logging.info(ret)

        # Display the info according to FREQUENCIES to verify it works properly
        # TODO(itspeter): Complete this test from specs given by RF team.
        for freq in FREQUENCIES:
            info_line = StringIO.StringIO()
            info_line.write("%8s MHz:" % (float(freq) / 1e6))
            for parameter in ret.traces:
                interpolated_value = ret.GetFreqResponse(freq, parameter)
                info_line.write("  %4s=%10g dB" %
                                (parameter, interpolated_value))
            logging.info("%s", info_line.getvalue())
