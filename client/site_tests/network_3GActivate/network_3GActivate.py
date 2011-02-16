# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import mock_modem, backchannel

import logging, re, socket, string, time, urllib2
import dbus, dbus.mainloop.glib, gobject

from autotest_lib.client.cros import flimflam_test_path
import flimflam, routing, mm

SERVER = 'testing-chargen.appspot.com'
BASE_URL = 'http://' + SERVER + '/'

IN_PROGRESS = 'org.chromium.flimflam.Error.InProgress'

class network_3GActivate(test.test):
    version = 1

    def Connect(self, service, config_timeout):
        """Attempts to connect

        Args:
            service: Cellular service object
            config_timeout:  Timeout (in seconds) before giving up on connect

        Raises:
            error.TestFail if connection fails
        """
        success, status = self.flim.ConnectService(
            service=service,
            config_timeout=config_timeout)
        if not success:
            raise error.TestFail('Could not connect: %s.' % status)

    def Disconnect(self, service, disconnect_timeout):
        """Attempts to disconnect

        Args:
            service: Cellular service object
            disconnect_timeout: Wait this long for disconnect to take
                effect.  Raise error.TestFail if we time out.
        """
        success, status = self.flim.DisconnectService(
            service=service,
            wait_timeout=disconnect_timeout)
        if not success:
            raise error.TestFail('Could not disconnect: %s.' % status)

    def Carrier(self):
        bus = dbus.SystemBus()
        obj = bus.get_object('org.chromium.ModemManager',
                             '/org/chromium/ModemManager/Carrier')
        return dbus.Interface(obj, 'org.chromium.ModemManager.Carrier')

    def ProcessPayment(self):
        carrier = self.Carrier()
        carrier.ProcessPayment()

    def ValidateServiceState(self, service, expected_state):
        state, time = self.flim.WaitForServiceState(
            service, [expected_state], timeout=5)

        if state != expected_state:
            raise error.TestFail('state is %s expected %s' %
                                 (state, expected_state))

    def ValidateActivationState(self, service, expected_state):
        state, time = self.flim.WaitForServiceState(
            service, [expected_state], timeout=5,
            property_name='Cellular.ActivationState')

        if state != expected_state:
            raise error.TestFail('activation state is %s expected %s' %
                                 (state, expected_state))

    def ValidateConnectivityState(self, service, expected_state):
        state, time = self.flim.WaitForServiceState(
            service, [expected_state], timeout=15,
            property_name='ConnectivityState')

        if state != expected_state:
            raise error.TestFail('connectivity state is %s expected %s' %
                                 (state, expected_state))

    def Activate(self, service):
        """Activate (OTASP/OMADM) the cellular service)

        Args:
            service: Cellular service object

        Returns:
            new service object after modem has activated

        Raises:
            error.TestFail if the service is not found
        """
        try:
            service.ActivateCellularModem('BogusCarrier')
        except dbus.exceptions.DBusException, e:
            if e._dbus_error_name != IN_PROGRESS:
                raise e

        # Bogus sleep for modem activate and reset (or fail
        # activation)
        # Re-implement to wait for a signal or state change
        time.sleep(3)

        service = self.flim.FindCellularService()
        if not service:
            raise error.TestFail('No cellular service after activation')

        return service

    def GetMdn(self, device):
        properties = device.GetProperties()
        return properties.get('Cellular.MDN', None)

    def run_once_internal(self):
        bus_loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus(mainloop=bus_loop)

        service = self.flim.FindCellularService()
        self.ValidateActivationState(service, 'not-activated')

        service = self.Activate(service)
        self.ValidateActivationState(service, 'partially-activated')

        service = self.Activate(service)
        self.ValidateActivationState(service, 'partially-activated')
        self.ValidateServiceState(service, 'activation-failure')
        self.Connect(service, config_timeout=5)
        self.ValidateConnectivityState(service, 'restricted')

        # Allow activation to succeed
        self.ProcessPayment()

        self.Disconnect(service, disconnect_timeout=5)
        service = self.Activate(service)
        self.ValidateActivationState(service, 'activated')
        self.Connect(service, config_timeout=5)
        self.ValidateConnectivityState(service, 'unrestricted')
        self.ValidateServiceState(service, 'ready')


    def run_once(self):
        backchannel.setup()

        modem = mock_modem.Modem()

        # Set up the software modem
        try:
          # Hack need to wait until name server is working again
          time.sleep(1)
          modem.setup()
        except Exception, e:
          logging.error(e)
          backchannel.teardown()
          raise e

        time.sleep(3)
        self.flim = flimflam.FlimFlam()
        self.device_manager = flimflam.DeviceManager(self.flim)
        try:
            self.device_manager.ShutdownAllExcept('cellular')
            self.run_once_internal()
        finally:
            try:
                self.device_manager.RestoreDevices()
            finally:
                try:
                    modem.teardown()
                finally:
                    backchannel.teardown()
