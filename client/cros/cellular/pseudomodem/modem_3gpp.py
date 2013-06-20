# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import dbus.types
import logging

import connect_machine
import disconnect_machine
import mm1
import modem
import register_machine

class Modem3gpp(modem.Modem):
    """
    Pseudomodem implementation of the
    org.freedesktop.ModemManager1.Modem.Modem3gpp and
    org.freedesktop.ModemManager1.Modem.Simple interfaces. This class provides
    access to specific actions that may be performed in modems with 3GPP
    capabilities.

    """

    IMEI = '00112342342123'

    class GsmNetwork(object):
        """
        GsmNetwork stores the properties of a 3GPP network that can be
        discovered during a network scan.

        """
        def __init__(self,
                     operator_long,
                     operator_short,
                     operator_code,
                     status,
                     access_technology):
            self.status = status
            self.operator_long = operator_long
            self.operator_short = operator_short
            self.operator_code = operator_code
            self.access_technology = access_technology

    def _InitializeProperties(self):
        ip = modem.Modem._InitializeProperties(self)
        props = ip[mm1.I_MODEM]
        props3gpp = self._GetDefault3GPPProperties()
        if props3gpp:
            ip[mm1.I_MODEM_3GPP] = props3gpp
        props['SupportedCapabilities'] = [
                dbus.types.UInt32(mm1.MM_MODEM_CAPABILITY_GSM_UMTS),
                dbus.types.UInt32(mm1.MM_MODEM_CAPABILITY_LTE),
                dbus.types.UInt32(
                        mm1.MM_MODEM_CAPABILITY_GSM_UMTS |
                        mm1.MM_MODEM_CAPABILITY_LTE)
        ]
        props['CurrentCapabilities'] = dbus.types.UInt32(
                mm1.MM_MODEM_CAPABILITY_GSM_UMTS | mm1.MM_MODEM_CAPABILITY_LTE)
        props['MaxBearers'] = dbus.types.UInt32(3)
        props['MaxActiveBearers'] = dbus.types.UInt32(2)
        props['EquipmentIdentifier'] = self.IMEI
        props['AccessTechnologies'] = dbus.types.UInt32((
                mm1.MM_MODEM_ACCESS_TECHNOLOGY_GSM |
                mm1.MM_MODEM_ACCESS_TECHNOLOGY_UMTS))
        props['SupportedModes'] = [
                dbus.types.Struct([dbus.types.UInt32(mm1.MM_MODEM_MODE_3G |
                                                     mm1.MM_MODEM_MODE_4G),
                                   dbus.types.UInt32(mm1.MM_MODEM_MODE_4G)],
                                  signature='uu')
        ]
        props['CurrentModes'] = props['SupportedModes'][0]
        props['SupportedBands'] = [
            dbus.types.UInt32(mm1.MM_MODEM_BAND_EGSM),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_DCS),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_PCS),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_G850),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_U2100),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_U1800),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_U17IV),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_U800),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_U850)
        ]
        props['CurrentBands'] = [
            dbus.types.UInt32(mm1.MM_MODEM_BAND_EGSM),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_DCS),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_PCS),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_G850),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_U2100),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_U800),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_U850)
        ]
        return ip

    def _GetDefault3GPPProperties(self):
        if not self.sim or self.sim.locked:
            return None
        return {
            'Imei' : self.IMEI,
            'RegistrationState' : (
                    dbus.types.UInt32(
                        mm1.MM_MODEM_3GPP_REGISTRATION_STATE_IDLE)),
            'OperatorCode' : '',
            'OperatorName' : '',
            'EnabledFacilityLocks' : (
                    dbus.types.UInt32(self.sim.enabled_locks))
        }

    def UpdateLockStatus(self):
        """
        Overloads superclass implementation. Also updates
        'EnabledFacilityLocks' if 3GPP properties are exposed.

        """
        modem.Modem.UpdateLockStatus(self)
        if mm1.I_MODEM_3GPP in self._properties:
            self.SetUInt32(mm1.I_MODEM_3GPP,
                     'EnabledFacilityLocks',
                     self.sim.enabled_locks)

    def SetSIM(self, sim):
        """
        Overrides modem.Modem.SetSIM. Once the SIM has been assigned, attempts
        to expose 3GPP properties if SIM readable.

        @param sim: An instance of sim.SIM

        Emits:
            PropertiesChanged

        """
        modem.Modem.SetSIM(self, sim)
        self.Expose3GPPProperties()

    def Expose3GPPProperties(self):
        """
        A call to this method will attempt to expose 3GPP properties if there
        is a current SIM and is unlocked.

        """
        props = self._GetDefault3GPPProperties()
        if props:
            self.SetAll(mm1.I_MODEM_3GPP, props)

    def SetRegistrationState(self, state):
        """
        Sets the 'RegistrationState' property.

        @param state: An MMModem3gppRegistrationState value.

        Emits:
            PropertiesChanged

        """
        self.SetUInt32(mm1.I_MODEM_3GPP, 'RegistrationState', state)

    @dbus.service.method(mm1.I_MODEM_3GPP, in_signature='s')
    def Register(self, operator_id, *args):
        """
        Request registration with a given modem network.

        @param operator_id: The operator ID to register. An empty string can be
                            used to register to the home network.
        @param args: Args can optionally contain an operator name.

        """
        logging.info('Modem3gpp.Register: %s', operator_id)
        if operator_id:
            assert self.sim
            assert self.Get(mm1.I_MODEM, 'Sim') != mm1.ROOT_PATH
            if operator_id == self.sim.Get(mm1.I_SIM, 'OperatorIdentifier'):
                state = mm1.MM_MODEM_3GPP_REGISTRATION_STATE_HOME
            else:
                state = mm1.MM_MODEM_3GPP_REGISTRATION_STATE_ROAMING
        else:
            state = mm1.MM_MODEM_3GPP_REGISTRATION_STATE_HOME

        logging.info('Modem3gpp.Register: Setting registration state to %s.',
            mm1.RegistrationStateToString(state))
        self.SetRegistrationState(state)
        logging.info('Modem3gpp.Register: Setting state to REGISTERED.')
        self.ChangeState(mm1.MM_MODEM_STATE_REGISTERED,
            mm1.MM_MODEM_STATE_CHANGE_REASON_USER_REQUESTED)
        self.Set(mm1.I_MODEM_3GPP, 'OperatorCode', operator_id)
        if args:
            self.Set(mm1.I_MODEM_3GPP, 'OperatorName', args[0])

    @dbus.service.method(mm1.I_MODEM_3GPP, out_signature='aa{sv}')
    def Scan(self):
        """
        Scan for available networks.

        Returns:
            An array of dictionaries with each array element describing a
            mobile network found in the scan. See the ModemManager reference
            manual for the list of keys that may be included in the returned
            dictionary.

        """
        state = self.Get(mm1.I_MODEM, 'State')
        if state < mm1.MM_MODEM_STATE_ENABLED:
            raise mm1.MMCoreError(mm1.MMCoreError.WRONG_STATE,
                    'Modem not enabled, cannot scan for networks.')

        sim_path = self.Get(mm1.I_MODEM, 'Sim')
        if not self.sim:
            assert sim_path == mm1.ROOT_PATH
            raise mm1.MMMobileEquipmentError(
                mm1.MMMobileEquipmentError.SIM_NOT_INSERTED,
                'Cannot scan for networks because no SIM is inserted.')
        assert sim_path != mm1.ROOT_PATH

        # TODO(armansito): check here for SIM lock?

        scanned = [network.__dict__ for network in self.roaming_networks]

        # get home network
        sim_props = self.sim.GetAll(mm1.I_SIM)
        scanned.append({
            'status': mm1.MM_MODEM_3GPP_NETWORK_AVAILABILITY_AVAILABLE,
            'operator-long': sim_props['OperatorName'],
            'operator-short': sim_props['OperatorName'],
            'operator-code': sim_props['OperatorIdentifier'],
            'access-technology': self.sim.access_technology
        })
        return scanned

    def RegisterWithNetwork(self):
        register_machine.RegisterMachine(self).Step()

    def UnregisterWithNetwork(self):
        logging.info('Modem3gpp.UnregisterWithHomeNetwork')
        logging.info('Setting registration state to IDLE.')
        self.SetRegistrationState(mm1.MM_MODEM_3GPP_REGISTRATION_STATE_IDLE)
        logging.info('Setting state to ENABLED.')
        self.ChangeState(mm1.MM_MODEM_STATE_ENABLED,
            mm1.MM_MODEM_STATE_CHANGE_REASON_USER_REQUESTED)
        self.Set(mm1.I_MODEM_3GPP, 'OperatorName', '')
        self.Set(mm1.I_MODEM_3GPP, 'OperatorCode', '')

    def Connect(self, properties, return_cb, raise_cb):
        """
        Overriden from superclass.

        @param properties
        @param return_cb
        @param raise_cb

        """
        logging.info('Connect')
        connect_machine.ConnectMachine(
            self, properties, return_cb, raise_cb).Step()

    def Disconnect(self, bearer_path, return_cb, raise_cb, *return_cb_args):
        """
        Overriden from superclass.

        @param bearer_path
        @param return_cb
        @param raise_cb
        @param return_cb_args

        """
        logging.info('Disconnect: %s', bearer_path)
        disconnect_machine.DisconnectMachine(
            self, bearer_path, return_cb, raise_cb, return_cb_args).Step()

    def GetStatus(self):
        """
        Overriden from superclass.

        """
        modem_props = self.GetAll(mm1.I_MODEM)
        m3gpp_props = self.GetAll(mm1.I_MODEM_3GPP)
        retval = {}
        retval['state'] = modem_props['State']
        if retval['state'] == mm1.MM_MODEM_STATE_REGISTERED:
            retval['signal-quality'] = modem_props['SignalQuality'][0]
            retval['bands'] = modem_props['CurrentBands']
            retval['access-technology'] = self.sim.access_technology
            retval['m3gpp-registration-state'] = \
                m3gpp_props['RegistrationState']
            retval['m3gpp-operator-code'] = m3gpp_props['OperatorCode']
            retval['m3gpp-operator-name'] = m3gpp_props['OperatorName']
        return retval
    # TODO(armansito): implement
    # org.freedesktop.ModemManager1.Modem.Modem3gpp.Ussd, if needed
    # (in a separate class?)
