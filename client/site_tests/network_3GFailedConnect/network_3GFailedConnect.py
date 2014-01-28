# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import dbus.mainloop.glib
import logging
import os

from autotest_lib.client.bin import test
from autotest_lib.client.cros import backchannel
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.cellular.pseudomodem import pseudomodem_context

# Disable warning about flimflam_test_path not being used. It is used to set
# up the path to the flimflam module.
# pylint: disable=W0611
from autotest_lib.client.cros import flimflam_test_path, network
# pylint: enable=W0611
import flimflam

TEST_MODEMS_MODULE_PATH = os.path.join(os.path.dirname(__file__), 'files',
                                       'modems.py')

class network_3GFailedConnect(test.test):
    """
    Tests that 3G connect failures are handled by shill properly.

    This test will fail if a connect failure does not immediately cause the
    service to enter the Failed state.

    """
    version = 1

    def ConnectTo3GNetwork(self, config_timeout):
        """
        Attempts to connect to a 3G network using shill.

        @param config_timeout: Timeout (in seconds) before giving up on
                               connect.

        @raises: error.TestFail if connection fails.

        """
        logging.info('ConnectTo3GNetwork')
        service = self.flim.FindCellularService()
        if not service:
          raise error.TestFail('No cellular service available')

        try:
          service.Connect()
        except Exception as e:
          logging.error(e)

        state = self.flim.WaitForServiceState(
            service=service,
            expected_states=["ready", "portal", "online", "failure"],
            timeout=config_timeout)[0]

        if state != "failure":
            raise error.TestFail('Service state should be failure not %s' %
                                 state)

    def _run_once_internal(self, connect_count):
        bus_loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus(mainloop=bus_loop)

        # Get to a good starting state
        network.ResetAllModems(self.flim)

        for ii in xrange(connect_count):
            self.ConnectTo3GNetwork(config_timeout=15)

    def run_once(self, connect_count=4,
                 pseudo_modem=False, pseudomodem_family='3GPP'):
        with backchannel.Backchannel():
            with pseudomodem_context.PseudoModemManagerContext(
                    pseudo_modem,
                    {'test-module' : TEST_MODEMS_MODULE_PATH,
                     'test-modem-class' : 'GetFailConnectModem',
                     'test-modem-arg' : [pseudomodem_family]}):
                self.flim = flimflam.FlimFlam()
                self.device_manager = flimflam.DeviceManager(self.flim)
                try:
                    self.device_manager.ShutdownAllExcept('cellular')
                    self._run_once_internal(connect_count)
                finally:
                    self.device_manager.RestoreDevices()
