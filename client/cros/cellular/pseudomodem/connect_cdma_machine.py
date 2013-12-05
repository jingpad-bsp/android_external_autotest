# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

import connect_machine
import mm1

class ConnectCdmaMachine(connect_machine.ConnectMachine):
    """
    ConnectCdmaMachine handles CDMA specific logic that is involved in
    connecting to a network.

    """
    def _HandleRegisteredState(self):
        logging.info('ConnectCdmaMachine: Modem is REGISTERED.')
        assert not self._modem.IsPendingDisconnect()
        assert not self._modem.IsPendingEnable()
        assert not self._modem.IsPendingDisable()
        assert not self._modem.IsPendingRegister()

        # Check here that the network is activated. The UI should prevent
        # connecting to an unactivated service, but for tests, we want to be
        # sure that connect fails.
        network = self._modem.GetHomeNetwork()
        if not network.activated:
            logging.info('ConnectCdmaMachine: Service is not activated. Cannot'
                         ' connect.')
            self.raise_cb(mm1.MMCoreError(mm1.MMCoreError.FAILED,
                                          'Service not activated.'))
            return False

        logging.info('ConnectCdmaMachine: Setting state to CONNECTING.')
        reason = mm1.MM_MODEM_STATE_CHANGE_REASON_USER_REQUESTED
        self._modem.ChangeState(mm1.MM_MODEM_STATE_CONNECTING, reason)
        return True

    def _GetModemStateFunctionMap(self):
        fmap = super(ConnectCdmaMachine, self)._GetModemStateFunctionMap()
        fmap[mm1.MM_MODEM_STATE_REGISTERED] = \
            ConnectCdmaMachine._HandleRegisteredState
        return fmap
