# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import dbus.types
import mm1
import modem
import modem_simple


class ModemCdma(modem.Modem, modem_simple.ModemSimple):
    """
    Pseudomodem implementation of the
    org.freedesktop.ModemManager1.Modem.ModemCdma and
    org.freedesktop.ModemManager1.Modem.Simple interfaces. This class provides
    access to specific actions that may be performed in modems with CDMA
    capabilities.

    """

    def _InitializeProperties(self):
        ip = modem.Modem._InitializeProperties(self)
        ip[mm1.I_MODEM_CDMA] = {
            'Meid' : 'A100000DCE2CA0',
            'Esn' : 'EDD1EDD1',
            'Sid' : dbus.types.UInt32(0),
            'Nid' : dbus.types.UInt32(0),
            'Cdma1xRegistrationState' : (
            dbus.types.UInt32(mm1.MM_MODEM_CDMA_REGISTRATION_STATE_UNKNOWN)),
            'EvdoRegistrationState' : (
            dbus.types.UInt32(mm1.MM_MODEM_CDMA_REGISTRATION_STATE_UNKNOWN))
        }
        props = ip[mm1.I_MODEM]
        props['ModemCapabilities'] = (
            dbus.types.UInt32(mm1.MM_MODEM_CAPABILITY_CDMA_EVDO))
        props['CurrentCapabilities'] = (
            dbus.types.UInt32(mm1.MM_MODEM_CAPABILITY_CDMA_EVDO))
        props['MaxBearers'] = dbus.types.UInt32(1)
        props['MaxActiveBearers'] = dbus.types.UInt32(1)
        props['EquipmentIdentifier'] = props['Meid']
        props['AccessTechnologies'] = (
            dbus.types.UInt32(mm1.MM_MODEM_ACCESS_TECHNOLOGY_1XRTT))
        props['SupportedModes'] = dbus.types.UInt32(mm1.MM_MODEM_MODE_ANY)
        props['AllowedModes'] = props['SupportedModes']
        props['PreferredMode'] = dbus.types.UInt32(mm1.MM_MODEM_MODE_NONE)
        props['SupportedBands'] = [
            dbus.types.UInt32(mm1.MM_MODEM_BAND_CDMA_BC0_CELLULAR_800),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_CDMA_BC1_PCS_1900),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_CDMA_BC2_TACS),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_CDMA_BC3_JTACS),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_CDMA_BC4_KOREAN_PCS),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_CDMA_BC5_NMT450),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_CDMA_BC6_IMT2000),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_CDMA_BC7_CELLULAR_700),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_CDMA_BC8_1800),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_CDMA_BC9_900),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_CDMA_BC10_SECONDARY_800),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_CDMA_BC11_PAMR_400)
        ]
        props['Bands'] = [
            dbus.types.UInt32(mm1.MM_MODEM_BAND_CDMA_BC0_CELLULAR_800),
            dbus.types.UInt32(mm1.MM_MODEM_BAND_CDMA_BC1_PCS_1900),
        ]
        return ip

    @dbus.service.method(mm1.I_MODEM_CDMA, in_signature='s')
    def Activate(self, carrier):
    """
    Provisions the modem for use with a given carrier using the modem's
    OTA activation functionality, if any.

    Args:
        carrier -- Name of carrier

    Emits:
        ActivationStateChanged

    """
        raise NotImplementedError()

    @dbus.service.method(mm1.I_MODEM_CDMA, in_signature='a{sv}')
    def ActivateManual(self, properties):
    """
    Sets the modem provisioning data directly, without contacting the carrier
    over the air. Some modems will reboot after this call is made.

    Args:
        properties -- A dictionary of properties to set on the modem, including
                      "mdn" and "min"

    Emits:
        ActivationStateChanged

    """
        raise NotImplementedError()

    @dbus.service.signal(mm1.I_MODEM_CDMA, signature='uua{sv}')
    def ActivationStateChanged(
            self,
            activation_state,
            activation_error,
            status_changes):
        raise NotImplementedError()

    # TODO(armansito): implement ModemSimple
