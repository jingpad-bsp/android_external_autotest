# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import time
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server import autotest
from autotest_lib.server.cros import stress
from autotest_lib.server.cros.network import wifi_cell_test_base

_DELAY = 10
_CLIENT_TERMINATION_FILE_PATH = '/tmp/simple_login_exit'


class network_WiFi_SuspendStress(wifi_cell_test_base.WiFiCellTestBase):
    """Uses servo to repeatedly close & open lid while running BrowserTests."""
    version = 1


    def parse_additional_arguments(self, commandline_args, additional_params):
        """Hook into super class to take control files parameters.

        @param commandline_args dict of parsed parameters from the autotest.
        @param additional_params list of tuple(HostapConfig,
                                               AssociationParameters).
        """
        self._configurations = additional_params


    def logged_in(self):
        """Checks if the host has a logged in user.

        @return True if a user is logged in on the device.

        """
        try:
            out = self._host.run('cryptohome --action=status').stdout
        except:
            return False
        try:
            status = json.loads(out.strip())
        except ValueError:
            logging.info('Cryptohome did not return a value.')
            return False

        success = any((mount['mounted'] for mount in status['mounts']))
        if success:
            # Chrome needs a few moments to get ready, otherwise an immediate
            # suspend will power down the system.
            time.sleep(5)
        return success


    def stress_wifi_suspend(self):
        """Perform the suspend stress."""
        self._host.servo.lid_close()
        self._host.wait_down(timeout=_DELAY)
        self._host.servo.lid_open()
        self._host.wait_up(timeout=_DELAY)
        state_info = self.context.wait_for_connection(
            self.context.router.get_ssid())
        self._timings.append(state_info.time)


    def exit_client(self):
        """End the client side test."""
        self._host.run('touch %s' % _CLIENT_TERMINATION_FILE_PATH)


    def run_once(self, suspends=5):
        self._host = self.context.client.host
        for router_conf, client_conf in self._configurations:
            self.context.configure(router_conf)
            assoc_params = xmlrpc_datatypes.AssociationParameters(
                ssid=self.context.router.get_ssid())
            self.context.assert_connect_wifi(assoc_params)

            self._timings = list()

            autotest_client = autotest.Autotest(self._host)
            stressor = stress.CountedStressor(self.stress_wifi_suspend,
                                              on_exit=self.exit_client)
            stressor.start(suspends, start_condition=self.logged_in)
            autotest_client.run_test('desktopui_SimpleLogin')
            stressor.wait()

            perf_dict = {'fastest': max(self._timings),
                         'slowest': min(self._timings),
                         'average': (float(sum(self._timings)) /
                                     len(self._timings))}
            for key in perf_dict:
                self.output_perf_value(description=key,
                    value=perf_dict[key],
                    units='seconds',
                    higher_is_better=False,
                    graph=router_conf.perf_loggable_description)


    def cleanup(self):
        """Cold reboot the device so the WiFi card is back in a good state."""
        self._host.servo.get_power_state_controller().reset()
