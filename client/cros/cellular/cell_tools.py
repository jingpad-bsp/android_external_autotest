# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities for cellular tests."""
import copy, dbus, logging, os, string, tempfile

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.cellular import cellular

from autotest_lib.client.cros import flimflam_test_path
import flimflam, mm

class Error(Exception):
    pass


TIMEOUT=30


def ConnectToCellular(flim, timeout=TIMEOUT):
    """Attempts to connect to a cell network using FlimFlam.

    Args:
    flim:  A flimflam object
    timeout:    Timeout (in seconds) before giving up on connect

    Raises:
    Error if connection fails or times out
    """
    service = flim.FindCellularService()
    if not service:
        raise Error('Could not find cell service')
    properties = service.GetProperties(utf8_strings = True)
    logging.error('Properties are: %s', properties)

    logging.info('Connecting to cell service: %s', service)
    success, status = flim.ConnectService(
        service=service,
        assoc_timeout=timeout,
        config_timeout=timeout)

    if not success:
        logging.error('Connect failed: %s' % status)
        # TODO(rochberg):  Turn off autoconnect
        if 'Error.AlreadyConnected' not in status['reason']:
            raise Error('Could not connect: %s.' % status)

    connected_states = ['portal', 'online']
    # We have to wait up to 10 seconds for state to go to portal
    state = flim.WaitForServiceState(service=service,
                                     expected_states=connected_states,
                                     timeout=timeout,
                                     ignore_failure=True)[0]
    if not state in connected_states:
        raise Error('Still in state %s' % state)

    return (service, state)


def FindLastGoodAPN(service, default=None):
    if not service:
        return default
    props = service.GetProperties()
    if 'Cellular.LastGoodAPN' not in props:
        return default
    last_good_apn = props['Cellular.LastGoodAPN']
    return last_good_apn.get('apn', default)


def DisconnectFromCellularService(bs, flim, service):
    """Attempts to disconnect from the supplied cellular service.

    Args:
        bs:  A basestation object.  Pass None to skip basestation-side checks
        flim:  A flimflam object
        service:  A cellular service object
    """

    flim.DisconnectService(service)  # Waits for flimflam state to go to idle

    if bs:
        verifier = bs.GetAirStateVerifier()
        # This is racy: The modem is free to report itself as
        # disconnected before it actually finishes tearing down its RF
        # connection.
        verifier.AssertDataStatusIn([
            cellular.UeGenericDataStatus.DISCONNECTING,
            cellular.UeGenericDataStatus.REGISTERED,
            cellular.UeGenericDataStatus.NONE,])

        def _ModemIsFullyDisconnected():
            return verifier.IsDataStatusIn([
                cellular.UeGenericDataStatus.REGISTERED,
                cellular.UeGenericDataStatus.NONE,])

        utils.poll_for_condition(
            _ModemIsFullyDisconnected,
            timeout=20,
            exception=Error('modem not disconnected from base station'))


def _EnumerateModems(manager):
    """Get a set of modem paths."""
    return set([x[1] for x in mm.EnumerateDevices(manager)])


def _SawNewModem(manager, preexisting_modems, old_modem):
    current_modems = _EnumerateModems(manager)
    if old_modem in current_modems:
        return False
    # NB: This fails if an unrelated modem disappears.  Not fixing
    # until we support > 1 modem
    return preexisting_modems != current_modems


def _WaitForModemToReturn(manager, preexisting_modems_original, modem_path):
    preexisting_modems = copy.copy(preexisting_modems_original)
    preexisting_modems.remove(modem_path)

    utils.poll_for_condition(
        lambda : _SawNewModem(manager, preexisting_modems, modem_path),
        timeout=50,
        exception=Error('Modem did not come back after settings change'))

    current_modems = _EnumerateModems(manager)

    new_modems = [x for x in current_modems - preexisting_modems]
    if len(new_modems) != 1:
        raise Error('Unexpected modem list change: %s vs %s' % (
            current_modems, new_modems))

    logging.info('New modem: %s' % new_modems[0])
    return new_modems[0]


def SetFirmwareForTechnologyFamily(manager, modem_path, family):
    """Set the modem to firmware.  Return potentially-new modem path."""
    preexisting_modems = _EnumerateModems(manager)

    # We do not currently support any multi-family modems besides Gobi
    gobi = manager.GobiModem(modem_path)
    if not gobi:
        raise Error('Modem %s does not support %s, cannot change technologies' %
                    modem_path, family)

    logging.info('Changing firmware to technology family %s' % family)

    FamilyToCarrierString = {
            cellular.TechnologyFamily.UMTS: 'Generic UMTS',
            cellular.TechnologyFamily.CDMA: 'Verizon Wireless',}

    gobi.SetCarrier(FamilyToCarrierString[family])
    return _WaitForModemToReturn(manager, preexisting_modems, modem_path)


# A test PRL that has an ID of 3333 and sets the device to aquire the
# default config of an 8960 with system_id 331.  Base64 encoding
# Generated with "base64 < prl"

TEST_PRL_3333 = (
    'ADENBQMAAMAAAYADAgmABgIKDQsEAYAKDUBAAQKWAAIAQGAJApYAAgAw8BAAAAD/Uw=='.
    decode('base64_codec'))


# A modem with this MDN will always report itself as activated
TESTING_MDN = dbus.String("1115551212", variant_level=1)


def _IsCdmaModemConfiguredCorrectly(manager, modem_path):
    """Returns true iff the CDMA modem at modem_path is configured correctly."""
    # We don't test for systemID because the PRL should take care of
    # that.

    status = manager.SimpleModem(modem_path).GetStatus()

    required_settings = {'mdn': TESTING_MDN,
                         'min': TESTING_MDN,
                         'prl_version': 3333}
    configured_correctly = True

    for rk, rv in required_settings.iteritems():
        if rk not in status or rv != status[rk]:
            logging.error('_CheckCdmaModemStatus:  %s: expected %s, got %s' % (
                rk, rv, status.get(rk)))
            configured_correctly = False
    return configured_correctly


def PrepareCdmaModem(manager, modem_path):
    """Configure a CDMA device (including PRL, MIN, and MDN)."""

    if _IsCdmaModemConfiguredCorrectly(manager, modem_path):
        return modem_path

    logging.info('Updating modem settings')
    preexisting_modems = _EnumerateModems(manager)
    cdma = manager.CdmaModem(modem_path)

    with tempfile.NamedTemporaryFile() as f:
        os.chmod(f.name, 0744)
        f.write(TEST_PRL_3333)
        f.flush()
        logging.info('Calling ActivateManual to change PRL')

        cdma.ActivateManual({
            'mdn': TESTING_MDN,
            'min': TESTING_MDN,
            'prlfile': dbus.String(f.name, variant_level=1),
            'system_id':  dbus.UInt16(331, variant_level=1), # Default 8960 SID
            'spc': dbus.String('000000'),})
        new_path = _WaitForModemToReturn(
            manager, preexisting_modems, modem_path)

    if not _IsCdmaModemConfiguredCorrectly(manager, new_path):
        raise Error('Modem configuration failed')
    return new_path


def GetCurrentTechnologyFamily(manager, modem_path):
  """Returns the technology family of the specified modem."""

  try:
      manager.GetAll(mm.ModemManager.GSM_CARD_INTERFACE, modem_path)
      return cellular.TechnologyFamily.UMTS
  except dbus.exceptions.DBusException:
      return cellular.TechnologyFamily.CDMA


def PrepareModemForTechnology(modem_path, target_technology):
    """Prepare modem for the technology: Sets things like firmware, PRL."""

    manager, modem_path = mm.PickOneModem(modem_path)

    logging.info('Found modem %s' % modem_path)

    current_family = GetCurrentTechnologyFamily(manager, modem_path)
    target_family = cellular.TechnologyToFamily[target_technology]

    if current_family != target_family:
        modem_path = SetFirmwareForTechnologyFamily(
            manager, modem_path, target_family)

    if target_family == cellular.TechnologyFamily.CDMA:
        modem_path = PrepareCdmaModem(manager, modem_path)

    return modem_path


def FactoryResetModem(modem_pattern, spc='000000'):
    """Factory resets modem, returns DBus pathname of modem after reset."""
    manager, modem_path = mm.PickOneModem(modem_pattern)
    preexisting_modems = _EnumerateModems(manager)
    modem = manager.Modem(modem_path)
    modem.FactoryReset(spc)
    return _WaitForModemToReturn(manager, preexisting_modems, modem_path)


class OtherDeviceShutdownContext(object):
    """Context manager that shuts down other devices.
    Usage:
    with cell_tools.OtherDeviceShutdownContext(flim, 'cellular'):
    block

    TODO(rochberg):  Replace flimflam.DeviceManager with this
    """
    def __init__(self, device_type, flim):
        self.device_manager = flimflam.DeviceManager(flim)
        self.device_manager.ShutdownAllExcept(device_type)

    def __enter__(self):
        return self

    def __exit__(self, exception, value, traceback):
        self.device_manager.RestoreDevices()
        return False


class BlackholeContext(object):
    """Context manager which uses IP tables to black hole access to hosts

    A host in hosts can be either a hostname or an IP address.  Using a
    hostname is potentially troublesome here due to DNS inconsistencies
    and load balancing, but iptables is generally smart with hostnames,
    inserting rules for each of the N ip addresses returned by a name
    lookup.

    Usage:
        with cell_tools.BlackholeContext(hosts):
            block
    """

    def __init__(self, hosts):
        self.hosts = hosts

    def _rules(self):
        rules = utils.system_output('iptables -S OUTPUT').splitlines()
        rules += utils.system_output('iptables -S INPUT').splitlines()
        return set(rules)

    def __enter__(self):
        """Preserve original list of rules and blacklist self.hosts"""
        self.original_rules = self._rules()

        for host, chain in self.hosts:
            if chain == 'OUTPUT':
                host_flag = '-d'
            else:
                host_flag = '-s'
            cmd = ' '.join(['iptables',
                            '-I %s' % chain,
                            '%s %s' % (host_flag, host),
                            '-j REJECT'])
            utils.run(cmd)
        return self

    def __exit__(self, exception, value, traceback):
        """ Remove all rules not in the original list."""
        for rule in self._rules():
            if rule in self.original_rules:
                logging.info('preserving %s' % rule)
                continue
            rule = string.replace(rule, '-A', '-D', 1)
            logging.info('removing %s' % rule)
            utils.run('iptables %s' % rule)

        return False


class AutoConnectContext(object):
    """Context manager which sets autoconnect to either true or false

       Enable or Disable autoconnect for the cellular service.
       Restore it when done.

       Usage:
           with cell_tools.DisableAutoConnectContext(device, flim, autoconnect):
               block
    """

    def __init__(self, device, flim, autoconnect):
        self.device = device
        self.flim = flim
        self.autoconnect = autoconnect
        self.autoconnect_changed = False

    def PowerOnDevice(self, device):
        """Power on a flimflam device, ignoring in progress errors."""
        logging.info('powered = %s' % device.GetProperties()['Powered'])
        if device.GetProperties()['Powered']:
            return
        try:
            device.Enable()
        except dbus.exceptions.DBusException, e:
            if e._dbus_error_name != 'org.chromium.flimflam.Error.InProgress':
                raise e

    def __enter__(self):
        """Power up device, get the service and disable autoconnect."""
        changed = False
        self.PowerOnDevice(self.device)

        # TODO(jglasgow): generalize to use services associated with device
        service = self.flim.FindCellularService(timeout=40)
        if not service:
            raise error.TestFail('No cellular service available.')

        props = service.GetProperties()
        favorite = props['Favorite']

        if not favorite:
            logging.info('Enabling Favorite by connecting to service.')
            ConnectToCellular(self.flim)
            props = service.GetProperties()
            favorite = props['Favorite']

        autoconnect = props['AutoConnect']
        logging.info('Favorite = %s, AutoConnect = %s' % (
            favorite, autoconnect))

        if autoconnect != self.autoconnect:
            logging.info('Setting AutoConnect = %s.', self.autoconnect)
            service.SetProperty('AutoConnect', dbus.Boolean(self.autoconnect))

            props = service.GetProperties()
            favorite = props['Favorite']
            autoconnect = props['AutoConnect']
            changed = True

        if not favorite:
            raise error.TestFail('Favorite=False, but we want it to be True')

        if autoconnect != self.autoconnect:
            raise error.TestFail('AutoConnect is %s, but we want it to be %s' %
                                 (autoconnect, self.autoconnect))

        self.autoconnect_changed = changed

        return self

    def __exit__(self, exception, value, traceback):
        """Restore autoconnect state if we changed it."""
        if not self.autoconnect_changed:
            return

        try:
            self.PowerOnDevice(self.device)
        except Exception as e:
            if exception:
                logging.error(
                    'Exiting AutoConnectContext with one exception, but ' +
                    'PowerOnDevice raised another')
                logging.error(
                    'Swallowing PowerOnDevice exception %s' % e)
                return False
            else:
                raise e

        # TODO(jglasgow): generalize to use services associated with
        # device, and restore state only on changed services
        service = self.flim.FindCellularService()
        if not service:
            logging.error('Cannot find cellular service.  '
                          'Autoconnect state not restored.')
            return
        service.SetProperty('AutoConnect', dbus.Boolean(not self.autoconnect))

        return False
