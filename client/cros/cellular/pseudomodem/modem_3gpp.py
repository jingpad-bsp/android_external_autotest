# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import dbus.types
import gobject
import logging
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

    class GsmNetwork(object):
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

    def SetRegistrationState(self, state):
        self.SetUInt32(
            mm1.I_MODEM_3GPP, 'RegistrationState', dbus.types.UInt32(state))

    class RegisterStep(modem.Modem.StateMachine):
        def Step(self, *args):
            if self.cancelled:
                self.modem.register_step = None
                return

            state = self.modem.Get(mm1.I_MODEM, 'State')
            if self.modem.register_step and self.modem.register_step != self:
                logging.info('There is an ongoing Register operation.')
                raise mm1.MMCoreError(mm1.MMCoreError.IN_PROGRESS,
                        'Register operation already in progress.')
            elif not self.modem.register_step:
                if state == mm1.MM_MODEM_STATE_ENABLED:
                    logging.info('Starting Register.')
                    self.modem.register_step = self
                else:
                    message = ('Cannot initiate register while in state %d, '
                               'state needs to be ENABLED.') % state.
                    raise mm1.MMCoreError(mm1.MMCoreError.WRONG_STATE, message)

            reason = mm1.MM_MODEM_STATE_CHANGE_REASON_USER_REQUESTED

            if state == mm1.MM_MODEM_STATE_ENABLED:
                logging.info('RegisterStep: Modem is ENABLED.')
                logging.info('RegisterStep: Setting registration state '
                             'to SEARCHING.')
                self.modem.SetRegistrationState(
                    mm1.MM_MODEM_3GPP_REGISTRATION_STATE_SEARCHING)
                logging.info('RegisterStep: Setting state to SEARCHING.')
                self.modem.ChangeState(mm1.MM_MODEM_STATE_SEARCHING, reason)
                logging.info('RegisterStep: Starting network scan.')
                try:
                    networks = self.modem.Scan()
                except:
                    self.modem.register_step = None
                    logging.info('An error occurred during Scan.')
                    self.modem.ChangeState(mm1.MM_MODEM_STATE_ENABLED,
                        mm1.MODEM_STATE_CHANGE_REASON_UNKNOWN)
                    raise
                logging.info('RegisterStep: Found networks: ' + str(networks))
                gobject.idle_add(Modem3gpp.RegisterStep.Step, self, networks)
            elif state == mm1.MM_MODEM_STATE_SEARCHING:
                logging.info('RegisterStep: Modem is SEARCHING.')
                assert len(args) == 1
                networks = args[0]
                if not networks:
                    logging.info('RegisterStep: Scan returned no networks.')
                    logging.info('RegisterStep: Setting state to ENABLED.')
                    self.modem.ChangeState(mm1.MM_MODEM_STATE_ENABLED,
                        mm1.MM_MODEM_STATE_CHANGE_REASON_UNKNOWN)
                    # TODO(armansito): Figure out the correct registration
                    # state to transition to when no network is present.
                    logging.info(('RegisterStep: Setting registration state '
                                  'to IDLE.'))
                    self.modem.SetRegistrationState(
                        mm1.MM_MODEM_3GPP_REGISTRATION_STATE_IDLE)
                    self.modem.register_step = None
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
                    logging.info(('RegisterStep: Registering to network: ' +
                        str(networks[0])))
                    self.modem.Register(networks[0]['operator-code'],
                        networks[0]['operator-long'])

                    # Modem3gpp.Register() should have set the state to
                    # REGISTERED.
                    self.modem.register_step = None

    @dbus.service.method(mm1.I_MODEM_3GPP, in_signature='s')
    def Register(self, operator_id, *args):
        """
        Request registration with a given modem network.

        Args:
            operator_id -- The operator ID to register. An empty string can be
                           used to register to the home network.
            *args -- Args can optionally contain an operator name.

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
        Modem3gpp.RegisterStep(self).Step()

    class ConnectStep(modem.Modem.StateMachine):
        def __init__(self, modem, properties, return_cb, raise_cb):
            super(Modem3gpp.ConnectStep, self).__init__(modem)
            self.connect_props = properties
            self.return_cb = return_cb
            self.raise_cb = raise_cb
            self.enable_initiated = False
            self.register_initiated = False

        def Step(self):
            if self.cancelled:
                self.modem.connect_step = None
                return

            state = self.modem.Get(mm1.I_MODEM, 'State')
            if self.modem.connect_step:
                if self.modem.connect_step != self:
                    logging.info('There is an ongoing Connect oparation.')
                    e = mm1.MMCoreError(mm1.MMCoreError.IN_PROGRESS,
                        'Modem connect already in progress.')
                    self.raise_cb(e)
                    return
            else:
                if self.modem.IsPendingDisable():
                    logging.info(('Modem is currently being disabled. '
                                  'Ignoring connect.'))
                    e = mm1.MMCoreError(mm1.MMCoreError.WRONG_STATE,
                        'Modem is currently being disabled. Ignoring connect.')
                    self.raise_cb(e)
                    return
                if state == mm1.MM_MODEM_STATE_CONNECTED:
                    logging.info('Modem is already connected.')
                    e = mm1.MMCoreError(mm1.MMCoreError.CONNECTED,
                        'Already connected.')
                    self.raise_cb(e)
                    return
                elif state == mm1.MM_MODEM_STATE_DISCONNECTING:
                    assert self.modem.IsPendingDisconnect()
                    logging.info('Cannot connect while disconnecting.')
                    e = mm1.MMCoreError(mm1.MMCoreError.WRONG_STATE,
                        'Cannot connect while disconnecting.')
                    self.raise_cb(e)
                    return

                logging.info('Starting Connect.')
                self.modem.connect_step = self

            # TODO(armansito): If sim is locked, unlock it
            reason = mm1.MM_MODEM_STATE_CHANGE_REASON_USER_REQUESTED
            if state == mm1.MM_MODEM_STATE_DISABLED:
                logging.info('ConnectStep: Modem is DISABLED.')
                assert not self.modem.IsPendingEnable()
                if self.enable_initiated:
                    logging.info('ConnectStep: Failed to enable modem.')
                    self.Cancel()
                    self.modem.connect_step = None
                    e = mm1.MMCoreError(mm1.MMCoreError.FAILED,
                        'Failed to enable modem.')
                    self.raise_cb(e)
                    return
                else:
                    logging.info('ConnectStep: Initiating Enable.')
                    self.enable_initiated = True
                    self.modem.Enable(True)

                    # state machine will spin until modem gets enabled,
                    # or if enable fails
                    gobject.idle_add(Modem3gpp.ConnectStep.Step, self)
            elif state == mm1.MM_MODEM_STATE_ENABLING:
                logging.info('ConnectStep: Modem is ENABLING.')
                assert self.modem.IsPendingEnable()
                logging.info('ConnectStep: Waiting for enable.')
                gobject.idle_add(Modem3gpp.ConnectStep.Step, self)
            elif state == mm1.MM_MODEM_STATE_ENABLED:
                logging.info('ConnectStep: Modem is ENABLED.')

                # Check to see if a register is going on, if not,
                # start register
                if self.register_initiated:
                    logging.info('ConnectStep: Register failed.')
                    self.Cancel()
                    self.modem.connect_step = None
                    e = mm1.MMCoreError(mm1.MMCoreError.FAILED,
                        'Failed to register to a network.')
                    self.raise_cb(e)
                    return
                else:
                    logging.info('ConnectStep: Waiting for Register.')
                    if not self.modem.IsPendingRegister():
                        try:
                            self.RegisterWithNetwork()
                        except Exception as e:
                            self.raise_cb(e)
                            return
                    self.register_initiated = True
                    gobject.idle_add(Modem3gpp.ConnectStep.Step, self)
            elif state == mm1.MM_MODEM_STATE_SEARCHING:
                logging.info('ConnectStep: Modem is SEARCHING.')
                logging.info('ConnectStep: Waiting for modem to register.')
                assert self.register_initiated
                assert self.modem.IsPendingRegister()
                gobject.idle_add(Modem3gpp.ConnectStep.Step, self)
            elif state == mm1.MM_MODEM_STATE_REGISTERED:
                logging.info('ConnectStep: Modem is REGISTERED.')
                assert not self.modem.IsPendingDisconnect()
                assert not self.modem.IsPendingEnable()
                assert not self.modem.IsPendingDisable()
                assert not self.modem.IsPendingRegister()
                logging.info('ConnectStep: Setting state to CONNECTING.')
                self.modem.ChangeState(mm1.MM_MODEM_STATE_CONNECTING, reason)
                gobject.idle_add(Modem3gpp.ConnectStep.Step, self)
            elif state == mm1.MM_MODEM_STATE_CONNECTING:
                logging.info('ConnectStep: Modem is CONNECTING.')
                assert not self.modem.IsPendingDisconnect()
                assert not self.modem.IsPendingEnable()
                assert not self.modem.IsPendingDisable()
                assert not self.modem.IsPendingRegister()
                try:
                    # try to find a matching data bearer
                    bearer = None
                    bearer_path = None
                    bearer_props = {}
                    for p, b in self.modem.bearers.iteritems():
                        # assemble bearer props
                        for key, val in self.connect_props.iteritems():
                            if key in modem.ALLOWED_BEARER_PROPERTIES:
                                bearer_props[key] = val
                        if (b.bearer_props == bearer_props):
                            logging.info('ConnectStep: Found matching bearer.')
                            bearer = b
                            bearer_path = p
                            break
                    if bearer is None:
                        assert bearer_path is None
                        logging.info(('ConnectStep: No matching bearer found, '
                            'creating brearer with properties: ' +
                            str(self.connect_props)))
                        bearer_path = self.modem.CreateBearer(bearer_props)
                    self.modem.ActivateBearer(bearer_path)
                    logging.info('ConnectStep: Setting state to CONNECTED.')
                    self.modem.ChangeState(mm1.MM_MODEM_STATE_CONNECTED, reason)
                    self.modem.connect_step = None
                    logging.info('ConnectStep: Returning bearer path: %s',
                        bearer_path)
                    self.return_cb(bearer_path)
                except Exception as e:
                    logging.info('ConnectStep: Failed to connect: ' + str(e))
                    self.raise_cb(e)
                    self.modem.ChangeState(mm1.MM_MODEM_STATE_REGISTERED,
                        mm1.MM_MODEM_STATE_CHANGE_REASON_UNKNOWN)
                    self.modem.connect_step = None

    def Connect(self, properties, return_cb, raise_cb):
        logging.info('Connect')
        Modem3gpp.ConnectStep(self, properties, return_cb, raise_cb).Step()

    class DisconnectStep(modem.Modem.StateMachine):
        def __init__(self, modem, bearer_path, return_cb, raise_cb,
            return_cb_args=[]):
            super(Modem3gpp.DisconnectStep, self).__init__(modem)
            self.bearer_path = bearer_path
            self.return_cb = return_cb
            self.raise_cb = raise_cb
            self.return_cb_args = return_cb_args

        def Step(self):
            if self.cancelled:
                self.modem.disconnect_step = None
                return

            state = self.modem.Get(mm1.I_MODEM, 'State')

            # If there is an ongoing disconnect that is not managed by this
            # instance, then return error.
            if self.modem.disconnect_step != self:
                message = 'There is an ongoing Disconnect operation.')
                logging.info(message)
                self.raise_cb(mm1.MMCoreError(mm1.MMCoreError.IN_PROGRESS,
                    message))
                return

            # If there is no ongoing disconnect, then initiate the process
            if not self.modem.disconnect_step:
                if state != mm1.MM_MODEM_STATE_CONNECTED:
                    message = 'Modem cannot be disconnected when not connected.'
                    logging.info(message)
                    self.raise_cb(
                        mm1.MMCoreError(mm1.MMCoreError.WRONG_STATE, message))
                    return

                assert self.modem.bearers
                assert self.modem.active_bearers

                if self.bearer_path == mm1.ROOT_PATH:
                    logging.info('All bearers will be disconnected.')
                elif not (self.bearer_path in self.modem.bearers):
                    message = ('Bearer with path "%s" not found' %
                               self.bearer_path)
                    logging.info(message)
                    self.raise_cb(
                        mm1.MMCoreError(mm1.MMCoreError.NOT_FOUND, message))
                    return
                elif not (self.bearer_path in self.modem.active_bearers):
                    message = ('No active bearer with path ' +
                        self.bearer_path +
                        ' found, current active bearers are ' +
                        str(self.modem.active_bearers))
                    logging.info(message)
                    self.raise_cb(mm1.MMCoreError(
                        mm1.MMCoreError.NOT_FOUND, message))
                    return

                assert not self.modem.IsPendingConnect()
                assert not self.modem.IsPendingEnable()
                assert not self.modem.IsPendingRegister

                logging.info('Starting Disconnect.')
                self.modem.disconnect_step = self

            # At this point, there is an ongoing disconnect operation managed
            # by this instance.

            reason = mm1.MM_MODEM_STATE_CHANGE_REASON_USER_REQUESTED
            if state == mm1.MM_MODEM_STATE_CONNECTED:
                logging.info('DisconnectStep: Modem state is CONNECTED.')
                logging.info('DisconnectStep: Setting state to DISCONNECTING.')
                self.modem.ChangeState(mm1.MM_MODEM_STATE_DISCONNECTING, reason)
                gobject.idle_add(Modem3gpp.DisconnectStep.Step, self)
            elif state == mm1.MM_MODEM_STATE_DISCONNECTING:
                logging.info('DisconnectStep: Modem state is DISCONNECTING.')
                assert not self.modem.IsPendingConnect()
                assert not self.modem.IsPendingEnable()
                assert not self.modem.IsPendingRegister()
                assert self.modem.active_bearers
                assert self.modem.bearers

                dc_reason = reason
                try:
                    if self.bearer_path == mm1.ROOT_PATH:
                        for bearer in self.modem.active_bearers.keys():
                            self.modem.DeactivateBearer(bearer)
                    else:
                        self.modem.DeactivateBearer(self.bearer_path)
                except Exception as e:
                    logging.info(('DisconnectStep: Failed to disconnect: ' +
                        str(e)))
                    dc_reason = mm1.MM_MODEM_STATE_CHANGE_REASON_UNKNOWN
                    self.raise_cb(e)
                finally:
                    # TODO(armansito): What should happen in a disconnect
                    # failure? Should we stay connected or become REGISTERED?
                    logging.info('DisconnectStep: Setting state to REGISTERED.')
                    self.modem.ChangeState(mm1.MM_MODEM_STATE_REGISTERED,
                        dc_reason)
                    self.modem.disconnect_step = None
                    logging.info('DisconnectStep: Calling return callback.')
                    self.return_cb(*self.return_cb_args)

    def Disconnect(self, bearer_path, return_cb, raise_cb, *return_cb_args):
        logging.info('Disconnect: %s' % bearer_path)
        Modem3gpp.DisconnectStep(
            self, bearer_path, return_cb, raise_cb, return_cb_args).Step()

    def GetStatus(self):
        modem_props = self.GetAll(mm1.I_MODEM)
        m3gpp_props = self.GetAll(mm1.I_MODEM_3GPP)
        retval = {}
        retval['state'] = modem_props['State']
        if retval['state'] == mm1.MM_MODEM_STATE_REGISTERED:
            retval['signal-quality'] = modem_props['SignalQuality'][0]
            retval['bands'] = modem_props['Bands']
            retval['access-technology'] = self.sim.access_technology
            retval['m3gpp-registration-state'] =
                m3gpp_props['RegistrationState']
            retval['m3gpp-operator-code'] = m3gpp_props['OperatorCode']
            retval['m3gpp-operator-name'] = m3gpp_props['OperatorName']
        return retval
    # TODO(armansito): implement
    # org.freedesktop.ModemManager1.Modem.Modem3gpp.Ussd, if needed
    # (in a separate class?)
