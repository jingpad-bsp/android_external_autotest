# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import dbus.types
import logging

import mm1
import modem
import register_machine_cdma

class ModemCdma(modem.Modem):
    """
    Pseudomodem implementation of the
    org.freedesktop.ModemManager1.Modem.ModemCdma and
    org.freedesktop.ModemManager1.Modem.Simple interfaces. This class provides
    access to specific actions that may be performed in modems with CDMA
    capabilities.

    """

    class CdmaNetwork(object):
        def __init__(self,
                     sid=99998,
                     nid=0,
                     activated=True,
                     standard='evdo'):
            self.sid = sid
            self.nid = nid
            self.standard = standard
            self.activated = activated

    def __init__(self,
                 home_network,
                 bus=None,
                 device='pseudomodem0',
                 roaming_networks=[],
                 config=None):
        self.home_network = home_network
        modem.Modem.__init__(self,
                             bus=bus,
                             device=device,
                             roaming_networks=roaming_networks,
                             config=config)

    def _InitializeProperties(self):
        ip = modem.Modem._InitializeProperties(self)
        if self.home_network and self.home_network.activated:
            activation_state = mm1.MM_MODEM_CDMA_ACTIVATION_STATE_ACTIVATED
        else:
            activation_state = mm1.MM_MODEM_CDMA_ACTIVATION_STATE_NOT_ACTIVATED
        ip[mm1.I_MODEM_CDMA] = {
            'Meid' : 'A100000DCE2CA0',
            'Esn' : 'EDD1EDD1',
            'Sid' : dbus.types.UInt32(0),
            'Nid' : dbus.types.UInt32(0),
            'Cdma1xRegistrationState' : (
            dbus.types.UInt32(mm1.MM_MODEM_CDMA_REGISTRATION_STATE_UNKNOWN)),
            'EvdoRegistrationState' : (
            dbus.types.UInt32(mm1.MM_MODEM_CDMA_REGISTRATION_STATE_UNKNOWN)),
            'ActivationState' : dbus.types.UInt32(activation_state)
        }
        props = ip[mm1.I_MODEM]
        props['ModemCapabilities'] = (
            dbus.types.UInt32(mm1.MM_MODEM_CAPABILITY_CDMA_EVDO))
        props['CurrentCapabilities'] = (
            dbus.types.UInt32(mm1.MM_MODEM_CAPABILITY_CDMA_EVDO))
        props['MaxBearers'] = dbus.types.UInt32(1)
        props['MaxActiveBearers'] = dbus.types.UInt32(1)
        props['EquipmentIdentifier'] = ip[mm1.I_MODEM_CDMA]['Meid']
        props['AccessTechnologies'] = (
            dbus.types.UInt32(mm1.MM_MODEM_ACCESS_TECHNOLOGY_EVDO0))
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
        Sets the modem provisioning data directly, without contacting the
        carrier over the air. Some modems will reboot after this call is made.

        Args:
            properties -- A dictionary of properties to set on the modem,
                          including "mdn" and "min"

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

    def GetHomeNetwork(self):
        return self.home_network

    def SetRegistered(self, network):
        logging.info('ModemCdma.SetRegistered')
        if network:
            state = mm1.MM_MODEM_CDMA_REGISTRATION_STATE_HOME
            sid = network.sid
            nid = network.nid
            if network.activated:
                activation_state = mm1.MM_MODEM_CDMA_ACTIVATION_STATE_ACTIVATED
            else:
                activation_state = \
                    mm1.MM_MODEM_CDMA_ACTIVATION_STATE_NOT_ACTIVATED
        else:
            state = mm1.MM_MODEM_CDMA_REGISTRATION_STATE_UNKNOWN
            sid = 0
            nid = 0
            activation_state = mm1.MM_MODEM_CDMA_ACTIVATION_STATE_NOT_ACTIVATED
        self.SetRegistrationState(state)
        self.SetUInt32(mm1.I_MODEM_CDMA, 'ActivationState', activation_state)
        self.SetUInt32(mm1.I_MODEM_CDMA, 'Sid', sid)
        self.SetUInt32(mm1.I_MODEM_CDMA, 'Nid', nid)

    def SetRegistrationState(self, state):
        self.SetUInt32(mm1.I_MODEM_CDMA, 'Cdma1xRegistrationState', state)
        self.SetUInt32(mm1.I_MODEM_CDMA, 'EvdoRegistrationState', state)

    # Inherited from modem.Modem.
    def RegisterWithNetwork(self):
        logging.info('ModemCdma.RegisterWithNetwork')
        register_machine_cdma.RegisterMachineCdma(self).Step()

    def UnregisterWithNetwork(self):
        logging.info('ModemCdma.UnregisterWithNetwork')
        if self.Get(mm1.I_MODEM, 'State') != \
            mm1.MM_MODEM_STATE_REGISTERED:
            logging.info('Currently not registered. Nothing to do.')
            return
        logging.info('Setting state to ENABLED.')
        self.ChangeState(mm1.MM_MODEM_STATE_ENABLED,
            mm1.MM_MODEM_STATE_CHANGE_REASON_USER_REQUESTED)
        logging.info('Unregistering.')
        self.SetRegistered(None)

    # Inherited from modem_simple.ModemSimple.
    def Connect(self, properties, return_cb, raise_cb):
        logging.info('ModemCdma.Connect')
        # Import connect_machine_cdma here to avoid circular imports.
        import connect_machine_cdma
        connect_machine_cdma.ConnectMachineCdma(
            self, properties, return_cb, raise_cb).Step()

    def Disconnect(self, bearer_path, return_cb, raise_cb, *return_cb_args):
        logging.info('ModemCdma.Disconnect: %s' % bearer_path)
        # Import connect_machine_cdma here to avoid circular imports.
        import disconnect_machine
        disconnect_machine.DisconnectMachine(
            self, bearer_path, return_cb, raise_cb, return_cb_args).Step()

    def GetStatus(self):
        modem_props = self.GetAll(mm1.I_MODEM)
        cdma_props = self.GetAll(mm1.I_MODEM_CDMA)
        retval = {}
        retval['state'] = modem_props['State']
        if retval['state'] == mm1.MM_MODEM_STATE_REGISTERED:
            retval['signal-quality'] = modem_props['SignalQuality'][0]
            retval['bands'] = modem_props['Bands']
            retval['access-technology'] = self.sim.access_technology
            retval['cdma-cdma1x-registration-state'] = \
                cdma_props['Cdma1xRegistrationState']
            retval['cdma-evdo-registration-state'] = \
                cdma_props['EvdoRegistrationState']
            retval['m3gpp-registration-state'] = \
                m3gpp_props['RegistrationState']
            retval['cdma-sid'] = cdma_props['Sid']
            retval['cdma-nid'] = cdma_props['Nid']
        return retval
