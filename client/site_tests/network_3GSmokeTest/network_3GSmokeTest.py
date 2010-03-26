# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

import logging, os, re, string, sys, time
import dbus, dbus.mainloop.glib, gobject

sys.path.append("/usr/local/lib/connman/test")
import mm

class network_3GSmokeTest(test.test):
    version = 1

    # TODO(jglasgow): temporary until we have a connman python library
    def FindCellularService(self):
        """Find the dbus cellular service object"""

        manager = dbus.Interface(self.bus.get_object("org.moblin.connman", "/"),
            "org.moblin.connman.Manager")

        properties = manager.GetProperties()

        for path in properties["Services"]:
            service = dbus.Interface(self.bus.get_object("org.moblin.connman",
                                                         path),
                                     "org.moblin.connman.Service")
            service_properties = service.GetProperties()

            try:
                if service_properties["Type"] == 'cellular':
                    return service
            except KeyError:
                continue

        return None

    def WaitForServiceState(self, service, expected_state, timeout):
        """Wait until the service enters the expected_state or times out.

        This will return the state and the amount of time it took to
        get there.  If the state is 'failure' we return immediately
        without waiting for the timeout
        """

        start_time = time.time()
        timeout = start_time + timeout
        while time.time() < timeout:
            properties = service.GetProperties()
            state = properties.get("State", None)

            if state == "failure":
                break

            if state == expected_state:
                break
            time.sleep(.5)

        config_time = time.time() - start_time

        return (state, config_time)


    def ConnectTo3GNetwork(self, config_timeout):
        """Attempts to connect to a 3G network using FlimFlam."""

        service = self.FindCellularService()
        if not service:
            logging.error("FAIL(FindCellularService): no cell service found")
            return 1

        try:
            service.Connect()
        except Exception, e:
            logging.error("FAIL(Connect): exception %s", e)
            return 2

        # wait config_timeout seconds to get an ip address
        state, config_time = self.WaitForServiceState(service,
                                                      "ready",
                                                      config_timeout)

        if config_time > config_timeout:
            logging.error("TIMEOUT(config): %3.1f secs", config_time)
            return 3

        if state != "ready":
            logging.error("INVALID_STATE(config): %s after %3.1f secs",
                          state, config_time)
            return 4

        self.write_perf_keyval({"secs_config_time": config_time})

        logging.info('SUCCESS: config %3.1f secs state %s',
                     config_time, state)
        return 0

    def DisconnectFrom3GNetwork(self, disconnect_timeout):
        """Attempts to disconnect to a 3G network using FlimFlam."""
        service = self.FindCellularService()
        if not service:
            logging.error("FAIL(FindCellularService): no cell service found")
            return

        try:
            service.Disconnect()
        except dbus.exceptions.DBusException, e:
            if e.get_dbus_name() != 'org.moblin.connman.Error.InProgress':
                logging.error("FAIL(Disconnect): exception %s", e)
                return

        # wait timeout seconds for disconnect to succeed
        state, disconnect_time = self.WaitForServiceState(service,
                                                           "idle",
                                                           disconnect_timeout)

        if disconnect_time >= disconnect_timeout:
            logging.error("TIMEOUT(config): %3.1f secs", disconnect_time)
            return

        if state != "idle":
            logging.error("INVALID_STATE(disconnect): %s after %3.1f secs",
                          state, config_time)
            return

        self.write_perf_keyval({"secs_disconnect_time": disconnect_time})

        logging.info('SUCCESS: config %3.1f secs state %s' %
                     (disconnect_time, state))
        return 0

    def ResetAllModems(self):
        """Disable/Enable cycle all modems to ensure valid starting state."""
        manager = mm.ModemManager()

        for path in manager.manager.EnumerateDevices():

            modem = manager.Modem(path)
            modem.Enable(False)
            modem.Enable(True)


    def GetModemInfo(self):
        """Find all modems attached and return an dictionary of information.

        This returns a bunch of information for each modem attached to
        the system.  In practice collecting all this information
        sometimes fails if a modem is left in an odd state, so we
        collect as many things as we can to ensure that the modem is
        responding correctly.

        Returns: dictionary of information for each modem path
        """
        results = {}
        manager = mm.ModemManager()

        for path in manager.manager.EnumerateDevices():

            modem = manager.Modem(path)
            props = manager.Properties(path)

            try:
                info = dict(info=modem.GetInfo())
                modem_type = props['Type']
                if modem_type == mm.ModemManager.CDMA_MODEM:
                    cdma_modem = manager.CdmaModem(path)

                    info['esn'] = cdma_modem.GetEsn()
                    info['rs'] = cdma_modem.GetRegistrationState()
                    info['ss'] = cdma_modem.GetServingSystem()
                    info['quality'] = cdma_modem.GetSignalQuality()

                elif modem_type == mm.ModemManager.GSM_MODEM:
                    gsm_card = manager.GsmCard(path)
                    info['imsi'] = gsm_card.GetImsi()

                    gsm_network = manager.GsmNetwork(path)
                    info['ri'] = gsm_card.GetRegistrationInfo()

                else:
                    print 'Unknown modem type %s' % modem_type
                    continue

            except dbus.exceptions.DBusException, e:
                logging.error("MODEM_DBUS_FAILURE: %s: %s", path, e)
                continue

            results[path] = info

        return results

    def run_once(self):

        # Get to a good starting state
        self.ResetAllModems()

        # Get information about all the modems
        modem_info = self.GetModemInfo()
        logging.info("Info: %s" % ', '.join(modem_info))

        bus_loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus(mainloop=bus_loop)

        if self.ConnectTo3GNetwork(config_timeout=60) != 0:
            raise error.TestFail("Failed to connect")

        # TODO(jglasgow): Add code to validate connection

        if self.DisconnectFrom3GNetwork(disconnect_timeout=60) != 0:
            raise error.TestFail("Failed to disconnect")

        # Verify that we can still get information for all the modems
        logging.info("Info: %s" % ', '.join(modem_info))
        if len(self.GetModemInfo()) != len(modem_info):
            raise error.TestFail("Failed to leave modem in working state")
