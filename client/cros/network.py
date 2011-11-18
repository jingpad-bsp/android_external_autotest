# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from autotest_lib.client.cros import flimflam_test_path
from autotest_lib.client.common_lib import utils
import flimflam, mm


# TODO(rochberg):  Move modem-specific functions to cellular/cell_utils
def ResetAllModems(flim):
    """Disable/Enable cycle all modems to ensure valid starting state."""
    service = flim.FindCellularService()
    if not service:
        flim.EnableTechnology('cellular')
        service = flim.FindCellularService()

    logging.info('ResetAllModems: found service %s' % service)

    if service and service.GetProperties()['Favorite']:
        service.SetProperty('AutoConnect', False)

    for manager, path in mm.EnumerateDevices():
        modem = manager.Modem(path)
        modem.Enable(False)
        modem.Enable(True)


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

    def __init__(self):
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
        return self

    def __exit__(self, exception, value, traceback):
        self._CleanupRules()
        return False
