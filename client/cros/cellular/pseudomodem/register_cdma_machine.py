# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

import mm1
import register_machine

class RegisterCdmaMachine(register_machine.RegisterMachine):
    """
    RegisterCdmaMachine handles the CDMA specific state transitions involved in
    bringing the modem to the REGISTERED state.

    """
    def Cancel(self):
        """
        Cancel the current machine.

        Overwritten from parent class.
        """
        logging.info('RegisterCdmaMachine: Canceling register.')
        super(RegisterCdmaMachine, self).Cancel()
        state = self._modem.Get(mm1.I_MODEM, 'State')
        reason = mm1.MM_MODEM_STATE_CHANGE_REASON_USER_REQUESTED
        if state == mm1.MM_MODEM_STATE_SEARCHING:
            logging.info('RegisterCdmaMachine: Setting state to ENABLED.')
            self._modem.ChangeState(mm1.MM_MODEM_STATE_ENABLED, reason)
            self._modem.SetRegistrationState(
                mm1.MM_MODEM_CDMA_REGISTRATION_STATE_UNKNOWN)
        self._modem.register_step = None
        if self._raise_cb:
            self._raise_cb(
                    mm1.MMCoreError(mm1.MMCoreError.CANCELLED, 'Cancelled'))

    def _GetModemStateFunctionMap(self):
        return {
            mm1.MM_MODEM_STATE_ENABLED: RegisterCdmaMachine._HandleEnabledState,
            mm1.MM_MODEM_STATE_SEARCHING:
                RegisterCdmaMachine._HandleSearchingState
        }

    def _HandleEnabledState(self):
        logging.info('RegisterCdmaMachine: Modem is ENABLED.')
        logging.info('RegisterCdmaMachine: Setting state to SEARCHING.')
        self._modem.ChangeState(
            mm1.MM_MODEM_STATE_SEARCHING,
            mm1.MM_MODEM_STATE_CHANGE_REASON_USER_REQUESTED)
        return True

    def _HandleSearchingState(self):
        logging.info('RegisterCdmaMachine: Modem is SEARCHING.')
        network = self._modem.GetHomeNetwork()
        if not network:
            logging.info('RegisterCdmaMachine: No network available.')
            logging.info('RegisterCdmaMachine: Setting state to ENABLED.')
            self._modem.ChangeState(mm1.MM_MODEM_STATE_ENABLED,
                mm1.MM_MODEM_STATE_CHANGE_REASON_UNKNOWN)
            if self._raise_cb:
                self._raise_cb(mm1.MMMobileEquipmentError(
                        mm1.MMMobileEquipmentError.NO_NETWORK,
                        'No networks were found to register.'))
        else:
            logging.info(
                'RegisterCdmaMachine: Registering to network: ' + str(network))
            logging.info('RegisterCdmaMachine: Setting state to REGISTERED.')
            self._modem.ChangeState(
                mm1.MM_MODEM_STATE_REGISTERED,
                mm1.MM_MODEM_STATE_CHANGE_REASON_USER_REQUESTED)
        self._modem.SetRegistered(network)
        self._modem.register_step = None
        if self._return_cb:
            self._return_cb()
        return False
