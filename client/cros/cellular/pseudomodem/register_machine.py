# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

import mm1
import state_machine

class RegisterMachine(state_machine.StateMachine):
    def __init__(self, modem):
        super(RegisterMachine, self).__init__(modem)
        self._networks = None

    def Cancel(self):
        logging.info('RegisterMachine: Canceling register.')
        super(RegisterMachine, self).Cancel()
        state = self._modem.Get(mm1.I_MODEM, 'State')
        reason = mm1.MM_MODEM_STATE_CHANGE_REASON_USER_REQUESTED
        if state == mm1.MM_MODEM_STATE_SEARCHING:
            logging.info('RegisterMachine: Setting state to ENABLED.')
            self._modem.ChangeState(mm1.MM_MODEM_STATE_ENABLED, reason)
            self._modem.SetRegistrationState(
                mm1.MM_MODEM_3GPP_REGISTRATION_STATE_IDLE)
        self._modem.register_step = None

    def _HandleEnabledState(self):
        logging.info('RegisterMachine: Modem is ENABLED.')
        logging.info('RegisterMachine: Setting registration state '
                     'to SEARCHING.')
        self._modem.SetRegistrationState(
            mm1.MM_MODEM_3GPP_REGISTRATION_STATE_SEARCHING)
        logging.info('RegisterMachine: Setting state to SEARCHING.')
        reason = mm1.MM_MODEM_STATE_CHANGE_REASON_USER_REQUESTED
        self._modem.ChangeState(mm1.MM_MODEM_STATE_SEARCHING, reason)
        logging.info('RegisterMachine: Starting network scan.')
        try:
            self._networks = self._modem.Scan()
        except mm1.MMError as e:
            self._modem.register_step = None
            logging.error('An error occurred during network scan: ' + str(e))
            self._modem.ChangeState(mm1.MM_MODEM_STATE_ENABLED,
                mm1.MODEM_STATE_CHANGE_REASON_UNKNOWN)
            self._modem.SetRegistrationState(
                mm1.MM_MODEM_3GPP_REGISTRATION_STATE_IDLE)
            raise
        logging.info('RegisterMachine: Found networks: ' + str(self._networks))
        return True

    def _HandleSearchingState(self):
        logging.info('RegisterMachine: Modem is SEARCHING.')
        assert self._networks
        if not self._networks:
            logging.info('RegisterMachine: Scan returned no networks.')
            logging.info('RegisterMachine: Setting state to ENABLED.')
            self._modem.ChangeState(mm1.MM_MODEM_STATE_ENABLED,
                mm1.MM_MODEM_STATE_CHANGE_REASON_UNKNOWN)
            # TODO(armansito): Figure out the correct registration
            # state to transition to when no network is present.
            logging.info('RegisterMachine: Setting registration state '
                         'to IDLE.')
            self._modem.SetRegistrationState(
                mm1.MM_MODEM_3GPP_REGISTRATION_STATE_IDLE)
            self._modem.register_step = None
            raise mm1.MMMobileEquipmentError(
                mm1.MMMobileEquipmentError.NO_NETWORK,
                'No networks were found to register.')
        else:
            # For now pick the first network in the list.
            # Roaming networks will come before the home
            # network, so if the test provided any roaming
            # networks, we will register with the first one.
            # TODO(armansito): Could the operator-code not be
            # present or unknown?
            network = self._networks[0]
            logging.info(
                'RegisterMachine: Registering to network: ' + str(network))
            self._modem.Register(
                network['operator-code'], network['operator-long'])

            # Modem3gpp.Register() should have set the state to
            # REGISTERED.
            self._modem.register_step = None

    def _GetModemStateFunctionMap(self):
        return {
            mm1.MM_MODEM_STATE_ENABLED: RegisterMachine._HandleEnabledState,
            mm1.MM_MODEM_STATE_SEARCHING: RegisterMachine._HandleSearchingState
        }

    def _ShouldStartStateMachine(self):
        if self._modem.register_step and self._modem.register_step != self:
            # There is already an ongoing register operation.
            message = 'Register operation already in progress.'
            logging.info(message)
            raise mm1.MMCoreError(mm1.MMCoreError.IN_PROGRESS, message)
        elif self._modem.register_step is None:
            # There is no register operation going on, canceled or otherwise.
            state = self._modem.Get(mm1.I_MODEM, 'State')
            if state != mm1.MM_MODEM_STATE_ENABLED:
                message = 'Cannot initiate register while in state %d, ' \
                          'state needs to be ENABLED.' % state
                raise mm1.MMCoreError(mm1.MMCoreError.WRONG_STATE, message)

            logging.info('Starting Register.')
            self._modem.register_step = self
        return True
