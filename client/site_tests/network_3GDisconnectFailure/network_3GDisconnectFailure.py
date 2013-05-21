# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.cellular import cell_tools, mm
from autotest_lib.client.cros.cellular.pseudomodem import mm1
from autotest_lib.client.cros.cellular.pseudomodem import modem_3gpp
from autotest_lib.client.cros.cellular.pseudomodem import modem_cdma
from autotest_lib.client.cros.cellular.pseudomodem import pseudomodem

from autotest_lib.client.cros import backchannel, network, flimflam_test_path
import flimflam

CONNECT_CONFIG_TIMEOUT = 120
CONNECT_SERVICE_TIMEOUT = 30
DISCONNECT_TIMEOUT = 60

class DisconnectFailTest(object):
    """
    DisconnectFailTest implements common functionality in all test cases.

    """
    def __init__(self, pmm_context, test):
        self.pmm_context = pmm_context
        self.test_modem = None
        self.test = test
        self._SetupTestModem()

    def Run(self):
        """
        Runs the test.

        @raises test.TestFail, if |test_modem| hasn't been initialized.

        """
        if not self.test_modem:
            raise test.TestFail('Uninitialized test modem')
        self.pmm_context.SetModem(self.test_modem)
        self._RunTest()

    def _SetupTestModem(self):
        raise NotImplementedError()

    def _GetModemClass(self):
        if self.test.family == '3GPP':
            modem_class = modem_3gpp.Modem3gpp
        elif self.test.family == 'CDMA':
            modem_class = modem_cdma.ModemCdma
        else:
            raise error.TestError('Invalid pseudo modem family: ' + \
                                  str(self.test.family))
        return modem_class

    def _RunTest(self):
        raise NotImplementedError()

class DisconnectWhileStateIsDisconnectingTest(DisconnectFailTest):
    """
    Simulates a disconnect failure while the modem is still disconnecting.
    Fails if the service doesn't remain connected.

    """
    def _SetupTestModem(self):
        modem_class = self._GetModemClass()
        class _TestModem(modem_class):
            def Disconnect(
                self, bearer_path, return_cb, raise_cb, *return_cb_args):
                """
                Test implementation of
                org.freedesktop.ModemManager1.Modem.Simple.Disconnect. Sets the
                modem state to DISCONNECTING and then fails, fooling shill into
                thinking that the disconnect failed while disconnecting.

                Refer to modem_simple.ModemSimple.Connect for documentation.

                """
                # Proceed normally, if this Disconnect was initiated by a call
                # to Disable, which may happen due to auto-connect.
                if self.disable_step:
                    modem_class.Disconnect(
                        self, bearer_path, return_cb, raise_cb, return_cb_args)
                    return

                self.ChangeState(mm1.MM_MODEM_STATE_DISCONNECTING,
                                 mm1.MM_MODEM_STATE_CHANGE_REASON_UNKNOWN)
                time.sleep(5)
                raise mm1.MMCoreError(mm1.MMCoreError.FAILED)
        self.test_modem = _TestModem()

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
    def _SetupTestModem(self):
        modem_class = self._GetModemClass()
        class _TestModem(modem_class):
            def __init__(self):
                modem_class.__init__(self)
                self.disconnect_count = 0

            def Disconnect(
                self, bearer_path, return_cb, raise_cb, *return_cb_args):
                """
                Test implementation of
                org.freedesktop.ModemManager1.Modem.Simple.Disconnect. Keeps
                count of successive disconnect operations and fails during all
                but the first one.

                Refer to modem_simple.ModemSimple.Connect for documentation.

                """
                # Proceed normally, if this Disconnect was initiated by a call
                # to Disable, which may happen due to auto-connect.
                if self.disable_step:
                    modem_class.Disconnect(
                        self, bearer_path, return_cb, raise_cb, return_cb_args)
                    return

                # On the first call, set the state to DISCONNECTING.
                self.disconnect_count += 1
                if self.disconnect_count == 1:
                    self.ChangeState(mm1.MM_MODEM_STATE_DISCONNECTING,
                                     mm1.MM_MODEM_STATE_CHANGE_REASON_UNKNOWN)
                    time.sleep(5)
                else:
                    raise mm1.MMCoreError(mm1.MMCoreError.FAILED)
        self.test_modem = _TestModem()

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
        props = modem.GetAll(mm1.I_MODEM)
        if not props['State'] == mm1.MM_MODEM_STATE_DISCONNECTING:
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
    def _SetupTestModem(self):
        modem_class = self._GetModemClass()
        class _TestModem(modem_class):
            def Disconnect(
                self, bearer_path, return_cb, raise_cb, *return_cb_args):
                """
                Test implementation of
                org.freedesktop.ModemManager1.Modem.Simple.Disconnect.
                Fails with an error.

                Refer to modem_simple.ModemSimple.Connect for documentation.

                """
                # Proceed normally, if this Disconnect was initiated by a call
                # to Disable, which may happen due to auto-connect.
                if self.disable_step:
                    modem_class.Disconnect(
                        self, bearer_path, return_cb, raise_cb, return_cb_args)
                    return

                raise mm1.MMCoreError(mm1.MMCoreError.FAILED)
        self.test_modem = _TestModem()

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
        self.family = pseudomodem_family
        with backchannel.Backchannel():
            with pseudomodem.TestModemManagerContext(True) as tmmc:
                self.flim = flimflam.FlimFlam()
                self.device_manager = flimflam.DeviceManager(self.flim)
                self.flim.SetDebugTags(
                    'dbus+service+device+modem+cellular+portal+network+'
                    'manager+dhcp')

                tests = [
                    DisconnectWhileStateIsDisconnectingTest(
                        tmmc.GetPseudoModemManager(), self),
                    DisconnectWhileDisconnectInProgressTest(
                        tmmc.GetPseudoModemManager(), self),
                    DisconnectFailOtherTest(tmmc.GetPseudoModemManager(), self)
                ]

                try:
                    self.device_manager.ShutdownAllExcept('cellular')
                    for test in tests:
                        test.Run()
                finally:
                    self.device_manager.RestoreDevices()
