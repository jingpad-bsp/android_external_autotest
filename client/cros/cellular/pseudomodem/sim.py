# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import dbus_std_ifaces
import mm1

# TODO(armansito): Implement SIM locking mechanisms.

class SIM(dbus_std_ifaces.DBusProperties):
    """
    Pseudomodem implementation of the org.freedesktop.ModemManager1.Sim
    interface.

    Broadband modems usually need a SIM card to operate. Each Modem object will
    therefore expose up to one SIM object, which allows SIM-specific actions
    such as PIN unlocking.

    The SIM interface handles communication with SIM, USIM, and RUIM (CDMA SIM)
    cards.

    """

    class Carrier:

        MCC_LIST = {
            'test' : '001',
            'us': '310',
            'de': '262',
            'es': '214',
            'fr': '208',
            'gb': '234',
            'it': '222',
            'nl': '204'
        }

        CARRIER_LIST = {
            'test' : ('test', '000', 'Test Network'),
            'banana' : ('us', '001', 'Banana-Comm'),
            'att': ('us', '090', 'AT&T'),
            'tmobile': ('us', '026', 'T-Mobile'),
            'simyo': ('de', '03', 'simyo'),
            'movistar': ('es', '07', 'Movistar'),
            'sfr': ('fr', '10', 'SFR'),
            'three': ('gb', '20', '3'),
            'threeita': ('it', '99', '3ITA'),
            'kpn': ('nl', '08', 'KPN')
        }

        def __init__(self, carrier='banana'):
           carrier = self.CARRIER_LIST.get(carrier,
                self.CARRIER_LIST['banana'])

           self.mcc = self.MCC_LIST[carrier[0]]
           self.mnc = carrier[1]
           self.operator_name = carrier[2]
           if self.operator_name != 'Banana-Comm':
              self.operator_name = self.operator_name + ' - Fake'
           self.operator_id = self.mcc + self.mnc


    DEFAULT_MSIN = '1234567890'
    DEFAULT_IMSI = '888999111'

    def __init__(self,
                 carrier,
                 access_technology,
                 puk=None,
                 msin=DEFAULT_MSIN,
                 imsi=DEFAULT_IMSI,
                 config=None):
        if not carrier:
            raise TypeError('A carrier is required.')
        path = mm1.MM1 + '/SIM/0'
        self.msin = msin
        self.carrier = carrier
        self.imsi = carrier.operator_id + imsi
        dbus_std_ifaces.DBusProperties.__init__(self, path, None, config)
        self.puk = puk
        self.pin = None
        self.pin_enabled = False
        self.locked = False
        self.blocked = False
        self.access_technology = access_technology


    def _InitializeProperties(self):
        # TODO(armansito): some of these properties shouldn't be exposed
        # if the sim is locked
        props = {
            'SimIdentifier' : self.msin,
            'Imsi' : self.imsi,
            'OperatorIdentifier' : self.carrier.operator_id,
            'OperatorName' : self.carrier.operator_name
        }
        return { mm1.I_SIM : props }

    def IsLocked(self):
        return self.locked

    def IsBlocked(self):
        return self.blocked

    @dbus.service.method(mm1.I_SIM, in_signature='s')
    def SendPin(self, pin):
        """
        Sends the PIN to unlock the SIM card.

        Args:
            pin -- A string containing the PIN code.

        """
        raise NotImplementedError()

    @dbus.service.method(mm1.I_SIM, in_signature='ss')
    def SendPuk(self, puk, pin):
        """
        Sends the PUK and a new PIN to unlock the SIM card.

        Args:
            puk -- A string containing the PUK code.
            pin -- A string containing the PIN code.

        """
        raise NotImplementedError()

    @dbus.service.method(mm1.I_SIM, in_signature='sb')
    def EnablePin(self, pin, enabled):
        """
        Enables or disables PIN checking.

        Args:
            pin -- A string containing the PIN code.
            enabled -- TRUE to enable PIN, FALSE otherwise.

        """
        raise NotImplementedError()

    @dbus.service.method(mm1.I_SIM, in_signature='ss')
    def ChangePin(self, old_pin, new_pin):
        """
        Changes the PIN code.

        Args:
            old_pin -- A string containing the old PIN code.
            new_pin -- A string containing the new PIN code.

        """
        raise NotImplementedError()
