# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import dbus.types
import time

from autotest_lib.client.cros.cellular import mm1_constants
from autotest_lib.client.cros.cellular.pseudomodem import modem_3gpp
from autotest_lib.client.cros.cellular.pseudomodem import sim
from autotest_lib.client.cros.cellular.pseudomodem import utils as pm_utils

I_ACTIVATION_TEST = 'Interface.LTEActivationTest'

class TestModem(modem_3gpp.Modem3gpp):
    """
    Base class for the custom 3GPP fake modems that are defined in this test.

    """
    def _InitializeProperties(self):
        props = modem_3gpp.Modem3gpp._InitializeProperties(self)
        modem_props = props[mm1_constants.I_MODEM]
        modem_props['OwnNumbers'] = ['0000000000']
        modem_props['AccessTechnologies'] = dbus.types.UInt32(
            mm1_constants.MM_MODEM_ACCESS_TECHNOLOGY_LTE)
        modem_props['ModemCapabilities'] = dbus.types.UInt32(
            mm1_constants.MM_MODEM_CAPABILITY_LTE)
        modem_props['CurrentCapabilities'] = dbus.types.UInt32(
            mm1_constants.MM_MODEM_CAPABILITY_LTE)

        # For the purposes of this test, introduce a property to help
        # verify that a reset has taken place. Expose this under a test
        # specific interface.
        if hasattr(self, '_properties'):
            reset_called = \
                self._properties[I_ACTIVATION_TEST]['ResetCalled']
        else:
            reset_called = False
        props[I_ACTIVATION_TEST] = {
            'ResetCalled' : dbus.types.Boolean(reset_called)
        }
        return props


    def RegisterWithNetwork(
            self, operator_id='', return_cb=None, raise_cb=None):
        # Make this do nothing, so that we don't automatically
        # register to a network after enable.
        return


    @pm_utils.log_dbus_method()
    def Reset(self):
        self.Set(
            I_ACTIVATION_TEST, 'ResetCalled', dbus.types.Boolean(True))
        modem_3gpp.Modem3gpp.Reset(self)


class ResetRequiredForRegistrationModem(TestModem):
    """
    Fake modem that only becomes registered if it has been reset at least once.

    """
    def RegisterWithNetwork(
            self, operator_id='', return_cb=None, raise_cb=None):
        if self.Get(I_ACTIVATION_TEST, 'ResetCalled'):
            modem_3gpp.Modem3gpp.RegisterWithNetwork(
                    self, operator_id, return_cb, raise_cb)


class RetryRegistrationModem(TestModem):
    """
    Fake modem that becomes registered once registration has been triggered at
    least twice.

    """
    def __init__(self):
        super(RetryRegistrationModem, self).__init__()
        self.register_count = 0


    def RegisterWithNetwork(
            self, operator_id='', return_cb=None, raise_cb=None):
        # Make the initial registration due triggered by Enable do
        # nothing. We expect exactly two Enable commands:
        #   1. Triggered by shill to enable the modem,
        #   2. Triggered by ResetCellularDevice in
        #      ResetAfterRegisterTest.RunTest.
        self.register_count += 1
        if self.register_count > 1:
            modem_3gpp.Modem3gpp.RegisterWithNetwork(
                    self, operator_id, return_cb, raise_cb)


class TestSIM(sim.SIM):
    """ SIM instantiated with the default test network, for ease of use. """
    def __init__(self):
        # Shill's activating ICCID store tracks which SIM identifiers are in
        # the process of activation. If we use the same SIM identifier for
        # every test pass, then a failed test may leave a stale entry in the
        # activating ICCD store which will erroneously mark the SIM as pending
        # activation. So, to avoid this, try to use a unique SIM identifier
        # each time.
        sim_identifier = int(time.time())
        sim.SIM.__init__(
                self,
                sim.SIM.Carrier('test'),
                mm1_constants.MM_MODEM_ACCESS_TECHNOLOGY_LTE,
                msin=str(sim_identifier))
