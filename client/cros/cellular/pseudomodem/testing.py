# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus_std_ifaces
import logging

import mm1
import utils

class Testing(dbus_std_ifaces.DBusProperties):
    """
    The testing object allows the pseudomodem to be configured on the fly
    over D-Bus. It exposes a basic set of commands that can be used to
    simulate network events (such as SMS) or various other modem configurations
    that are needed for testing/debugging.

    """

    def __init__(self, modem, bus):
        self._modem = modem
        dbus_std_ifaces.DBusProperties.__init__(self, mm1.TESTING_PATH, bus)

    def _InitializeProperties(self):
        return { mm1.I_TESTING: { 'Modem': self._modem.path } }

    @utils.dbus_method_wrapper(logging.debug, logging.warning, mm1.I_TESTING,
                               in_signature='ss')
    def ReceiveSms(self, sender, text):
        """
        Simulates a fake SMS.

        @param sender: String containing the phone number of the sender.
        @param text: String containing the SMS message contents.

        """
        self._modem.sms_handler.receive_sms(text, sender)

    @utils.dbus_method_wrapper(logging.debug, logging.warning, mm1.I_TESTING,
                               in_signature='s')
    def UpdatePcoInfo(self, pco_value):
        """
        Sets the VendorPcoInfo to the specified value. If the Modem.Modem3gpp
        properties are currently not exposed (e.g. due to a locked or absent
        SIM), this method will do nothing.

        @param pco_value: The PCO string.

        """
        if mm1.I_MODEM_3GPP in self._modem.properties:
            self._modem.AssignPcoValue(pco_value)
