# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import logging

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

    DEFAULT_MSIN = '1234567890'
    DEFAULT_IMSI = '888999111'
    DEFAULT_PIN = '1111'
    DEFAULT_PUK = '12345678'

    class Carrier:
        """
        Represents a 3GPP carrier that can be stored by a SIM object.

        """
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

        def __init__(self, carrier='test'):
           carrier = self.CARRIER_LIST.get(carrier, self.CARRIER_LIST['test'])

           self.mcc = self.MCC_LIST[carrier[0]]
           self.mnc = carrier[1]
           self.operator_name = carrier[2]
           if self.operator_name != 'Banana-Comm':
              self.operator_name = self.operator_name + ' - Fake'
           self.operator_id = self.mcc + self.mnc

    def __init__(self,
                 carrier,
                 access_technology,
                 index=0,
                 pin=DEFAULT_PIN,
                 puk=DEFAULT_PUK,
                 locked=False,
                 msin=DEFAULT_MSIN,
                 imsi=DEFAULT_IMSI,
                 config=None):
        if not carrier:
            raise TypeError('A carrier is required.')
        path = mm1.MM1 + '/SIM/' + str(index)
        self.msin = msin
        self.carrier = carrier
        self.imsi = carrier.operator_id + imsi
        self._lock_data = {
            mm1.MM_MODEM_LOCK_SIM_PIN : [ pin, 3 ],
            mm1.MM_MODEM_LOCK_SIM_PUK : [ puk, 3 ]
        }
        self._lock_enabled = locked
        if locked:
            self._lock_type = mm1.MM_MODEM_LOCK_SIM_PIN
        else:
            self._lock_type = mm1.MM_MODEM_LOCK_NONE
        self._modem = None
        self.access_technology = access_technology
        dbus_std_ifaces.DBusProperties.__init__(self, path, None, config)

    def IncrementPath(self):
        """
        Increments the current index at which this modem is exposed on DBus.
        E.g. if the current path is org/freedesktop/ModemManager/Modem/0, the
        path will change to org/freedesktop/ModemManager/Modem/1.

        Calling this method does not remove the object from its current path,
        which means that it will be available via both the old and the new
        paths. This is currently only used by Reset, in conjunction with
        dbus_std_ifaces.DBusObjectManager.[Add|Remove].

        """
        self.index += 1
        path = mm1.MM1 + '/SIM/' + str(self.index)
        logging.info('SIM coming back as: ' + path)
        self.SetPath(path)

    @property
    def lock_type(self):
        """
        Returns the current lock type of the SIM. Can be used to determine
        whether or not the SIM is locked.

        @return The lock type, as a MMModemLock value.

        """
        return self._lock_type

    @property
    def unlock_retries(self):
        """
        Returns the number of unlock retries left.

        @return The number of unlock retries for each lock type the SIM
                supports as a dictionary.

        """
        retries = dbus.Dictionary(signature='uu')
        if not self._lock_enabled:
            return retries
        for k, v in self._lock_data.iteritems():
            retries[dbus.types.UInt32(k)] = dbus.types.UInt32(v[1])
        return retries

    @property
    def enabled_locks(self):
        """
        Returns the currently enabled facility locks.

        @return The currently enabled facility locks, as a MMModem3gppFacility
                value.

        """
        if self._lock_enabled:
            return mm1.MM_MODEM_3GPP_FACILITY_SIM
        return mm1.MM_MODEM_3GPP_FACILITY_NONE

    @property
    def locked(self):
        """
        @return True, if the SIM is locked. False, otherwise.

        """
        return not (self._lock_type == mm1.MM_MODEM_LOCK_NONE or
            self._lock_type == mm1.MM_MODEM_LOCK_UNKNOWN)

    @property
    def modem(self):
        """
        Returns the modem object that this SIM is currently plugged into.

        """
        return self._modem

    @modem.setter
    def modem(self, modem):
        """
        Assigns a modem object to this SIM, so that the modem knows about it.
        This should only be called directly by a modem object.

        @param modem: The modem to be associated with this SIM.

        """
        self._modem = modem

    def _DBusPropertiesDict(self):
        imsi = self.imsi
        if self.locked:
            msin = ''
            op_id = ''
            op_name = ''
        else:
            msin = self.msin
            op_id = self.carrier.operator_id
            op_name = self.carrier.operator_name
        return {
            'SimIdentifier' : msin,
            'Imsi' : imsi,
            'OperatorIdentifier' : op_id,
            'OperatorName' : op_name
        }

    def _InitializeProperties(self):
        return { mm1.I_SIM : self._DBusPropertiesDict() }

    def _ResetProperties(self):
        self.SetAll(mm1.I_SIM, self._DBusPropertiesDict())

    @dbus.service.method(mm1.I_SIM, in_signature='s')
    def SendPin(self, pin):
        """
        Sends the PIN to unlock the SIM card.

        @param pin: A string containing the PIN code.

        """
        raise NotImplementedError()

    @dbus.service.method(mm1.I_SIM, in_signature='ss')
    def SendPuk(self, puk, pin):
        """
        Sends the PUK and a new PIN to unlock the SIM card.

        @param puk: A string containing the PUK code.
        @param pin: A string containing the PIN code.

        """
        raise NotImplementedError()

    @dbus.service.method(mm1.I_SIM, in_signature='sb')
    def EnablePin(self, pin, enabled):
        """
        Enables or disables PIN checking.

        @param pin: A string containing the PIN code.
        @param enabled: TRUE to enable PIN, FALSE otherwise.

        """
        raise NotImplementedError()

    @dbus.service.method(mm1.I_SIM, in_signature='ss')
    def ChangePin(self, old_pin, new_pin):
        """
        Changes the PIN code.

        @param old_pin: A string containing the old PIN code.
        @param new_pin: A string containing the new PIN code.

        """
        raise NotImplementedError()
