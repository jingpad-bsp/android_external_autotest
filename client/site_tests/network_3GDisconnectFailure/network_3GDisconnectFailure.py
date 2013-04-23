# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

import logging, os, subprocess, time

from autotest_lib.client.cros import backchannel, network, flimflam_test_path
from autotest_lib.client.cros.cellular import cell_tools, mm
from autotest_lib.client.cros.cellular.pseudomodem import modem_3gpp
from autotest_lib.client.cros.cellular.pseudomodem import mm1, pseudomodem, sim
import flimflam

CONNECT_CONFIG_TIMEOUT = 120
CONNECT_SERVICE_TIMEOUT = 30
DISCONNECT_TIMEOUT = 60

class DisconnectFailTest(object):
    def __init__(self, pmm_context, test):
        self.pmm_context = pmm_context
        self.test_modem = None
        self.test = test
        self.SetupTestModem()

    def Run(self):
        if not self.test_modem:
            raise test.TestFail('Uninitialized test modem')
        self.pmm_context.SetModem(self.test_modem)
        self.RunTest()

    def SetupTestModem(self):
        raise NotImplementedError()

    def RunTest(self):
        raise NotImplementedError()

class DisconnectWhileStateIsDisconnectingTest(DisconnectFailTest):
    def SetupTestModem(self):
        class TestModem3gpp(modem_3gpp.Modem3gpp):
            def Disconnect(
                self, bearer_path, return_cb, raise_cb, *return_cb_args):
                self.ChangeState(mm1.MM_MODEM_STATE_DISCONNECTING,
                                 mm1.MM_MODEM_STATE_CHANGE_REASON_UNKNOWN)
                time.sleep(5)
                raise mm1.MMCoreError(mm1.MMCoreError.FAILED)
        self.test_modem = TestModem3gpp()

    def RunTest(self):
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
    def SetupTestModem(self):
        class TestModem3gpp(modem_3gpp.Modem3gpp):
            def __init__(self):
                modem_3gpp.Modem3gpp.__init__(self)
                self.disconnect_count = 0

            def Disconnect(
                self, bearer_path, return_cb, raise_cb, *return_cb_args):
                # On the first call, set the state to DISCONNECTING.
                self.disconnect_count += 1
                if self.disconnect_count == 1:
                    self.ChangeState(mm1.MM_MODEM_STATE_DISCONNECTING,
                                     mm1.MM_MODEM_STATE_CHANGE_REASON_UNKNOWN)
                    time.sleep(5)
                else:
                    raise mm1.MMCoreError(mm1.MMCoreError.FAILED)
        self.test_modem = TestModem3gpp()

    def RunTest(self):
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
    def SetupTestModem(self):
        class TestModem3gpp(modem_3gpp.Modem3gpp):
            def Disconnect(
                self, bearer_path, return_cb, raise_cb, *return_cb_args):
                raise mm1.MMCoreError(mm1.MMCoreError.FAILED)
        self.test_modem = TestModem3gpp()

    def RunTest(self):
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
    version = 1

    def IsServiceConnected(self):
        service = self.FindCellularService()
        properties = service.GetProperties(utf8_strings=True)
        state = properties.get('State', None)
        return state in ['portal', 'online']

    def IsServiceDisconnected(self):
        service = self.FindCellularService()
        properties = service.GetProperties(utf8_strings=True)
        state = properties.get('State', None)
        return state == 'idle'

    def FindCellularService(self):
        service = self.flim.FindCellularService()
        if not service:
            raise error.TestError('Could not find cellular service.')
        return service

    def run_once(self):
        with backchannel.Backchannel():
            fake_sim = sim.SIM(sim.SIM.Carrier('att'),
                mm1.MM_MODEM_ACCESS_TECHNOLOGY_GSM)
            with pseudomodem.TestModemManagerContext(True,
                                                     sim=fake_sim) as tmmc:
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
