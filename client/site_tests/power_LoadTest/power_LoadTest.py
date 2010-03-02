# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import os, logging, time
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, site_httpd, \
                                           site_power_status, site_ui


class power_LoadTest(test.test):
    version = 1

    def initialize(self):
        self.status = site_power_status.get_status()

        if self.status.linepower[0].online:
            raise error.TestNAError(
                  'This test needs to be run with the AC power offline')

        # TODO:
        # - Check that wifi is the active network interface
        # - Set brightness level
        # - Turn off screensaver/screen blanking
        # - Turn off suspend on idle

        # setup a HTTP Server to listen for status updates from the power
        # test extension
        self._testServer = site_httpd.HTTPListener(8001, docroot=self.bindir)
        self._testServer.run()


    def run_once(self, seconds=3600):
        # the power test extension will report its status here
        latch = self._testServer.add_wait_url('/status')

        # launch chrome with power test extension
        ext_path = os.path.join(self.bindir, 'extension')
        session = site_ui.ChromeSession('--load-extension=%s' % ext_path)

        time.sleep(seconds)
        session.close()

        if latch.is_set():
            logging.debug(self._testServer.get_form_entries())
        else:
            logging.debug("Power extension didn't report status!")

        # refresh battery stats
        self.status.refresh()


    def postprocess_iteration(self):
        keyvals = {}
        keyvals['ah_charge_full'] = self.status.battery[0].charge_full
        keyvals['ah_charge_full_design'] = \
                                self.status.battery[0].charge_full_design
        keyvals['ah_charge_now'] = self.status.battery[0].charge_now
        keyvals['a_current_now'] = self.status.battery[0].current_now
        keyvals['wh_energy'] = self.status.battery[0].energy
        keyvals['w_energy_rate'] = self.status.battery[0].energy_rate
        keyvals['h_remaining_time'] = self.status.battery[0].remaining_time
        keyvals['v_voltage_min_design'] = \
                                self.status.battery[0].voltage_min_design
        keyvals['v_voltage_now'] = self.status.battery[0].voltage_now

        self.write_perf_keyval(keyvals)
