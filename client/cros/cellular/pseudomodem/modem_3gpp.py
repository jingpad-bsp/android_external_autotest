# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import dbus.types
import mm1
import modem


class Modem3gpp(modem.Modem):
    """
    Pseudomodem implementation of the
    org.freedesktop.ModemManager1.Modem.Modem3gpp and
    org.freedesktop.ModemManager1.Modem.Simple interfaces. This class provides
    access to specific actions that may be performed in modems with 3GPP
    capabilities.

    """

    def _InitializeProperties(self):
        ip = modem.Modem._InitializeProperties(self)
        ip[mm1.I_MODEM_3GPP] = {
            'Imei' : '00112342342',
            'RegistrationState' : (
                dbus.types.UInt32(mm1.MM_MODEM_3GPP_REGISTRATION_STATE_IDLE)),
            'OperatorCode' : '',
            'OperatorName' : '',
            'EnabledFacilityLocks' : (
                dbus.types.UInt32(mm1.MM_MODEM_3GPP_FACILITY_NONE))
        }

        props = ip[mm1.I_MODEM]
        props['ModemCapabilities'] = dbus.types.UInt32(
            mm1.MM_MODEM_CAPABILITY_GSM_UMTS | mm1.MM_MODEM_CAPABILITY_LTE)
        props['CurrentCapabilities'] = dbus.types.UInt32(
            mm1.MM_MODEM_CAPABILITY_GSM_UMTS | mm1.MM_MODEM_CAPABILITY_LTE)
        props['MaxBearers'] = dbus.types.UInt32(3)
        props['MaxActiveBearers'] = dbus.types.UInt32(2)
        props['EquipmentIdentifier'] = ip[mm1.I_MODEM_3GPP]['Imei']
        props['AccessTechnologies'] = dbus.types.UInt32((
                mm1.MM_MODEM_ACCESS_TECHNOLOGY_GSM |
                mm1.MM_MODEM_ACCESS_TECHNOLOGY_UMTS))
        props['SupportedModes'] = dbus.types.UInt32(mm1.MM_MODEM_MODE_ANY)
        props['AllowedModes'] = props['SupportedModes']
        props['PreferredMode'] = dbus.types.UInt32(mm1.MM_MODEM_MODE_NONE)
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
        props['Bands'] = [
            dbus.types.UInt32(mm1.MM_MODEM_BAND_EGSM),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_DCS),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_PCS),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_G850),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_U2100),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_U800),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_U850)
        ]
        return ip

    @dbus.service.method(mm1.I_MODEM_3GPP, in_signature='s')
    def Register(self, operator_id):
        """
        Request registration with a given modem network.

        Args:
            operator_id -- The operator ID to register. An empty string can be
                            used to register to the home network.

        """
        raise NotImplementedError()

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
        raise NotImplementedError()

    # TODO(armansito): implement ModemSimple
    # TODO(armansito): implement
    # org.freedesktop.ModemManager1.Modem.Modem3gpp.Ussd, if needed
    # (in a separate class?)
