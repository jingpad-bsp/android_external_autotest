# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from autotest_lib.client.cros import flimflam_test_path
import flimflam, mm

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
        pass

    gobi = modem_manager.GobiModem(gobi_path)
    if gobi:
        gobi.InjectFault('ClearFaults',1);
