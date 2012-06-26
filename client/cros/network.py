# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus, logging, time

import common, flimflam_test_path
from autotest_lib.client.bin import utils
from autotest_lib.client.cros.cellular import mm


def _Bug24628WorkaroundEnable(modem):
    """Enable a modem.  Try again if a SerialResponseTimeout is received."""
    # http://code.google.com/p/chromium-os/issues/detail?id=24628
    tries = 5
    while tries > 0:
        try:
            modem.Enable(True)
            return
        except dbus.exceptions.DBusException, e:
            logging.error('Enable failed: %s' % e)
            tries -= 1
            if tries > 0:
                logging.error('_Bug24628WorkaroundEnable:  sleeping')
                time.sleep(6)
                logging.error('_Bug24628WorkaroundEnable:  retrying')
            else:
                raise


# TODO(rochberg):  Move modem-specific functions to cellular/cell_utils
def ResetAllModems(flim):
    """Disable/Enable cycle all modems to ensure valid starting state."""
    service = flim.FindCellularService()
    if not service:
        flim.EnableTechnology('cellular')
        service = flim.FindCellularService()

    logging.info('ResetAllModems: found service %s' % service)

    try:
        if service and service.GetProperties()['Favorite']:
            service.SetProperty('AutoConnect', False),
    except dbus.exceptions.DBusException, error:
        # The service object may disappear, we can safely ignore it.
        if error._dbus_error_name != 'org.freedesktop.DBus.Error.UnknownMethod':
            raise

    for manager, path in mm.EnumerateDevices():
        modem = manager.GetModem(path)
        version = modem.GetVersion()
        modem.Enable(False)
        utils.poll_for_condition(
            lambda: modem.IsDisabled(),
            exception=
                utils.TimeoutError('Timed out waiting for modem disable'),
            sleep_interval=1,
            timeout=30)
        if 'Y3300XXKB1' in version:
            _Bug24628WorkaroundEnable(modem)
        else:
            modem.Enable(True)
            utils.poll_for_condition(
                lambda: modem.IsEnabled(),
                exception=
                    utils.TimeoutError('Timed out waiting for modem enable'),
                sleep_interval=1,
                timeout=30)


def ClearGobiModemFaultInjection():
    """If there's a gobi present, try to clear its fault-injection state."""
    try:
        modem_manager, gobi_path = mm.PickOneModem('Gobi')
    except ValueError:
        # Didn't find a gobi
        return

    gobi = modem_manager.GobiModem(gobi_path)
    if gobi:
        gobi.InjectFault('ClearFaults',1);


class IpTablesContext(object):
    """Context manager that manages iptables rules."""
    IPTABLES='/sbin/iptables'

    def __init__(self, initial_allowed_host=None):
        self.initial_allowed_host = initial_allowed_host
        self.rules = []

    def _IpTables(self, command):
        # Run, log, return output
        return utils.system_output('%s %s' % (self.IPTABLES, command),
                                   retain_output=True)

    def _RemoveRule(self, rule):
        self._IpTables('-D ' + rule)
        self.rules.remove(rule)

    def AllowHost(self, host):
        for proto in ['tcp', 'udp']:
            rule = 'INPUT -s %s/32 -p %s -m %s -j ACCEPT' % (host, proto, proto)
            output = self._IpTables('-S INPUT')
            current = [x.rstrip() for x in output.splitlines()]
            logging.error('current: %s' % current)
            if '-A ' + rule in current:
                # Already have the rule
                logging.info('Not adding redundant %s' % rule)
                continue
            self._IpTables('-A '+ rule)
            self.rules.append(rule)

    def _CleanupRules(self):
        for rule in self.rules:
            self._RemoveRule(rule)

    def __enter__(self):
        if self.initial_allowed_host:
            self.AllowHost(self.initial_allowed_host)
        return self

    def __exit__(self, exception, value, traceback):
        self._CleanupRules()
        return False


def NameServersForService(flim, service):
    """Return the list of name servers used by a connected service."""
    service_properties = service.GetProperties(utf8_strings=True)
    device_path = service_properties['Device']
    device = flim.GetObjectInterface('Device', device_path)
    if device is None:
        logging.error('No device for service %s' % service)
        return []

    properties = device.GetProperties(utf8_strings=True)

    hosts = []
    for path in properties['IPConfigs']:
        ipconfig = flim.GetObjectInterface('IPConfig', path)
        ipconfig_properties = ipconfig.GetProperties(utf8_strings=True)
        hosts += ipconfig_properties['NameServers']

    logging.info('Name servers: %s', ', '.join(hosts))

    return hosts
