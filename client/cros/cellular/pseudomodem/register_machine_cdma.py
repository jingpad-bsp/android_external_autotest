# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

import mm1
import register_machine

class RegisterMachineCdma(register_machine.RegisterMachine):
    """
    RegisterMachineCdma handles the CDMA specific state transitions involved in
    bringing the modem to the REGISTERED state.

    """
    def Cancel(self):
        logging.info('RegisterMachineCdma: Canceling register.')
        super(RegisterMachine, self).Cancel()
        state = self._modem.Get(mm1.I_MODEM, 'State')
        reason = mm1.MM_MODEM_STATE_CHANGE_REASON_USER_REQUESTED
        if state == mm1.MM_MODEM_STATE_SEARCHING:
            logging.info('RegisterMachineCdma: Setting state to ENABLED.')
            self._modem.ChangeState(mm1.MM_MODEM_STATE_ENABLED, reason)
            self._modem.SetRegistrationState(
                mm1.MM_MODEM_CDMA_REGISTRATION_STATE_UNKNOWN)
        self._modem.register_step = None

    def _GetModemStateFunctionMap(self):
        return {
            mm1.MM_MODEM_STATE_ENABLED: RegisterMachineCdma._HandleEnabledState,
            mm1.MM_MODEM_STATE_SEARCHING:
                RegisterMachineCdma._HandleSearchingState
        }

    def _HandleEnabledState(self):
        logging.info('RegisterMachineCdma: Modem is ENABLED.')
        logging.info('RegisterMachineCdma: Setting state to SEARCHING.')
        self._modem.ChangeState(
            mm1.MM_MODEM_STATE_SEARCHING,
            mm1.MM_MODEM_STATE_CHANGE_REASON_USER_REQUESTED)
        return True

    def _HandleSearchingState(self):
        logging.info('RegisterMachineCdma: Modem is SEARCHING.')
        network = self._modem.GetHomeNetwork()
        if not network:
            logging.info('RegisterMachineCdma: No network available.')
            logging.info('RegisterMachineCdma: Setting state to ENABLED.')
            self._modem.ChangeState(mm1.MM_MODEM_STATE_ENABLED,
                mm1.MM_MODEM_STATE_CHANGE_REASON_UNKNOWN)
        else:
            logging.info(
                'RegisterMachineCdma: Registering to network: ' + str(network))
            logging.info('RegisterMachineCdma: Setting state to REGISTERED.')
            self._modem.ChangeState(
                mm1.MM_MODEM_STATE_REGISTERED,
                mm1.MM_MODEM_STATE_CHANGE_REASON_USER_REQUESTED)
        self._modem.SetRegistered(network)
        self._modem.register_step = None
        return False
