# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import time

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.cellular import cell_tools
from autotest_lib.client.cros.cellular import mm
from autotest_lib.client.cros.cellular import mm1_constants
from autotest_lib.client.cros.cellular.pseudomodem import pseudomodem_context

# Disable warning about flimflam_test_path not being used. It is used to set up
# the path to the flimflam module
# pylint: disable=W0611
from autotest_lib.client.cros import backchannel, network, flimflam_test_path
# pylint: enable=W0611
import flimflam

CONNECT_CONFIG_TIMEOUT = 120
CONNECT_SERVICE_TIMEOUT = 30
DISCONNECT_TIMEOUT = 60
TEST_MODEMS_MODULE_PATH = os.path.join(os.path.dirname(__file__), 'files',
                                       'modems.py')

class DisconnectFailTest(object):
    """
    DisconnectFailTest implements common functionality in all test cases.

    """
    def __init__(self, test, pseudomodem_family):
        self.test = test
        self._pseudomodem_family = pseudomodem_family


    def Run(self):
        """
        Runs the test.

        @raises test.TestFail, if |test_modem| hasn't been initialized.

        """
        with pseudomodem_context.PseudoModemManagerContext(
                True,
                {'test-module' : TEST_MODEMS_MODULE_PATH,
                 'test-modem-class' : self._GetTestModemFunctorName(),
                 'test-modem-arg' : [self._pseudomodem_family]}):
            self._RunTest()


    def _GetTestModemFunctorName(self):
        """ Returns the modem to be used by the pseudomodem for this test. """
        raise NotImplementedError()


    def _RunTest(self):
        raise NotImplementedError()


class DisconnectWhileStateIsDisconnectingTest(DisconnectFailTest):
    """
    Simulates a disconnect failure while the modem is still disconnecting.
    Fails if the service doesn't remain connected.

    """
    def _GetTestModemFunctorName(self):
        return 'GetModemDisconnectWhileStateIsDisconnecting'


    def _RunTest(self):
        network.ResetAllModems(self.test.flim)
        time.sleep(5)

        # Connect to the service if not already connected.
        if not self.test.IsServiceConnected():
            cell_tools.ConnectToCellular(self.test.flim)

        # Disconnect attempt should fail.
        service = self.test.FindCellularService()
        self.test.flim.DisconnectService(service=service,
                                         wait_timeout=DISCONNECT_TIMEOUT)

        # Service should remain connected.
        if not self.test.IsServiceConnected():
            raise error.TestError('Service should remain connected after '
                                  'disconnect failure.')


class DisconnectWhileDisconnectInProgressTest(DisconnectFailTest):
    """
    Simulates a disconnect failure on successive disconnects. Fails if the
    service doesn't remain connected.

    """
    def _GetTestModemFunctorName(self):
        return 'GetModemDisconnectWhileDisconnectInProgress'


    def _RunTest(self):
        network.ResetAllModems(self.test.flim)
        time.sleep(5)

        # Connect to the service if not already connected.
        if not self.test.IsServiceConnected():
            cell_tools.ConnectToCellular(self.test.flim)

        # Issue first disconnect. Service should remain connected.
        service = self.test.FindCellularService()
        self.test.flim.DisconnectService(service=service,
                                         wait_timeout=DISCONNECT_TIMEOUT)
        if not self.test.IsServiceConnected():
            raise error.TestError('Service should remain connected after '
                                  'first disconnect.')

        # Modem state should be disconnecting.
        manager, modem_path  = mm.PickOneModem('')
        modem = manager.GetModem(modem_path)
        props = modem.GetAll(mm1_constants.I_MODEM)
        if not props['State'] == mm1_constants.MM_MODEM_STATE_DISCONNECTING:
            raise error.TestError('Modem should be in the DISCONNECTING state.')

        # Issue second disconnect. Service should remain connected.
        self.test.flim.DisconnectService(service=service,
                                         wait_timeout=DISCONNECT_TIMEOUT)
        if not self.test.IsServiceConnected():
            raise error.TestError('Service should remain connected after '
                                  'disconnect failure.')


class DisconnectFailOtherTest(DisconnectFailTest):
    """
    Simulates a disconnect failure. Fails if the service doesn't disconnect.

    """
    def _GetTestModemFunctorName(self):
        return 'GetModemDisconnectFailOther'


    def _RunTest(self):
        network.ResetAllModems(self.test.flim)
        time.sleep(5)

        # Connect to the service if not already connected.
        if not self.test.IsServiceConnected():
            cell_tools.ConnectToCellular(self.test.flim)

        # Disconnect attempt should fail.
        service = self.test.FindCellularService()
        self.test.flim.DisconnectService(service=service,
                                         wait_timeout=DISCONNECT_TIMEOUT)

        # Service should be cleaned up as if disconnect succeeded.
        if not self.test.IsServiceDisconnected():
            raise error.TestError('Service should be disconnected.')


class network_3GDisconnectFailure(test.test):
    """
    The test uses the pseudo modem manager to simulate two failure scenarios of
    a Disconnect call: failure while the modem state is DISCONNECTING and
    failure while it is CONNECTED. The expected behavior of shill is to do
    nothing if the modem state is DISCONNECTING and to clean up the service
    otherwise.

    """
    version = 1

    def IsServiceConnected(self):
        """
        @return True, if service is connected.

        """
        service = self.FindCellularService()
        properties = service.GetProperties(utf8_strings=True)
        state = properties.get('State', None)
        return state in ['portal', 'online']


    def IsServiceDisconnected(self):
        """
        @return True, if service is disconnected.

        """
        service = self.FindCellularService()
        properties = service.GetProperties(utf8_strings=True)
        state = properties.get('State', None)
        return state == 'idle'


    def FindCellularService(self):
        """
        Looks for a cellular service.

        @return A Service DBus proxy object.
        @raises error.TestError, if no cellular service can be found.

        """
        service = self.flim.FindCellularService()
        if not service:
            raise error.TestError('Could not find cellular service.')
        return service


    def run_once(self, pseudomodem_family='3GPP'):
        with backchannel.Backchannel():
            self.flim = flimflam.FlimFlam()
            self.device_manager = flimflam.DeviceManager(self.flim)
            self.flim.SetDebugTags(
                'dbus+service+device+modem+cellular+portal+network+'
                'manager+dhcp')

            tests = [
                    DisconnectWhileStateIsDisconnectingTest(self,
                                                            pseudomodem_family),
                    DisconnectWhileDisconnectInProgressTest(self,
                                                            pseudomodem_family),
                    DisconnectFailOtherTest(self, pseudomodem_family),
            ]

            try:
                self.device_manager.ShutdownAllExcept('cellular')
                for test in tests:
                    test.Run()
            finally:
                self.device_manager.RestoreDevices()
