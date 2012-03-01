# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import network

from autotest_lib.client.cros.cellular import cell_tools
from autotest_lib.client.cros.cellular import environment
from autotest_lib.client.cros.cellular import modem

import time

from autotest_lib.client.cros import flimflam_test_path
import flimflam


class cellular_Signal(test.test):
    version = 1

    # The autotest infrastructure calls run_once.  The control file
    # fetches the JSON lab config and passes it in as a python object

    def run_once(self, config, technologies, wait_for_disc=True):

        technology = technologies[-1]
        with environment.DefaultCellularTestContext(config) as c:
            env = c.env
            flim = flimflam.FlimFlam()
            env.StartDefault(technology)
            network.ResetAllModems(flim)
            logging.info('Preparing for %s' % technology)
            cell_tools.PrepareModemForTechnology('', technology)

            # TODO(jglasgow) Need to figure out what isn't settling here.
            # Going to wait 'til after ResetAllModems changes land.
            time.sleep(10)

            service = env.CheckedConnectToCellular()

            # Step through all technologies, forcing a transition
            cell_modem = modem.PickOneModem('')
            for technology in technologies:
                env.emulator.Stop()
                if wait_for_disc:
                    utils.poll_for_condition(
                        lambda: not cell_modem.ModemIsRegistered(),
                        timeout=180,
                        exception=error.TestError(
                            'modem still registered to base station'))

                logging.info('Reconfiguring for %s' % technology)
                env.emulator.SetTechnology(technology)
                env.emulator.Start()

                utils.poll_for_condition(
                    lambda: cell_modem.ModemIsRegisteredUsing(technology),
                    timeout=60,
                    exception=error.TestError(
                        'modem is registerd using %s instead of %s' %
                        (cell_modem.GetAccessTechnology(), technology)))

                # TODO(jglasgow): verify flimflam properties (signals?)
