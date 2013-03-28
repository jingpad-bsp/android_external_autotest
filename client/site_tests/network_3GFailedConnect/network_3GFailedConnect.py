# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.cros import backchannel
from autotest_lib.client.common_lib import error

import logging, time
import dbus, dbus.mainloop.glib, gobject

from autotest_lib.client.cros.cellular.pseudomodem import mm1, pseudomodem, sim, modem_3gpp

from autotest_lib.client.cros import flimflam_test_path, network
import flimflam, mm

class FailConnectModem3gpp(modem_3gpp.Modem3gpp):
    """Custom fake Modem3gpp, that always fails to connect."""
    def Connect(self, properties, return_cb, raise_cb):
        logging.info('Connect call will fail.')
        raise_cb(mm1.MMCoreError(mm1.MMCoreError.FAILED))


class network_3GFailedConnect(test.test):
    version = 1

    def ConnectTo3GNetwork(self, config_timeout):
        """Attempts to connect to a 3G network using FlimFlam.

        Args:
        config_timeout:  Timeout (in seconds) before giving up on connect

        Raises:
        error.TestFail if connection fails
        """
        logging.info('ConnectTo3GNetwork')
        service = self.flim.FindCellularService()
        if not service:
          raise error.TestFail('No cellular service available')

        try:
          service.Connect()
        except Exception, e:
          print e

        state = self.flim.WaitForServiceState(
            service=service,
            expected_states=["ready", "portal", "online", "failure"],
            timeout=config_timeout)[0]

        if state != "failure":
            raise error.TestFail('Service state should be failure not %s' %
                                 state)

    def run_once_internal(self, connect_count):
        bus_loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus(mainloop=bus_loop)

        # Get to a good starting state
        network.ResetAllModems(self.flim)

        for ii in xrange(connect_count):
            self.ConnectTo3GNetwork(config_timeout=15)

    def run_once(self, connect_count=4, pseudo_modem=False):
        with backchannel.Backchannel():
            fake_sim = sim.SIM(sim.SIM.Carrier('att'),
                mm1.MM_MODEM_ACCESS_TECHNOLOGY_GSM)
            with pseudomodem.TestModemManagerContext(pseudo_modem,
                                                     ['cromo', 'modemmanager'],
                                                     sim=fake_sim,
                                                     modem=FailConnectModem3gpp()):
                self.flim = flimflam.FlimFlam()
                self.device_manager = flimflam.DeviceManager(self.flim)
                try:
                    self.device_manager.ShutdownAllExcept('cellular')
                    self.run_once_internal(connect_count)
                finally:
                    self.device_manager.RestoreDevices()
