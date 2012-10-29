#!/usr/bin/python

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import sys
import time

# Once these are no longer copied to DUTs manually, this should become
# from autotest_lib.client.common_lib.cros.site_wlan import constants
import constants

from site_wlan_dbus_setup import *

ssid         = sys.argv[1]
wait_timeout = int(sys.argv[2])

mprops = manager.GetProperties()
for path in mprops["Services"]:
    service = dbus.Interface(bus.get_object(constants.CONNECTION_MANAGER, path),
        constants.CONNECTION_MANAGER_SERVICE)
    sprops = service.GetProperties()
    if sprops.get("Name", None) != ssid:
        continue
    wait_time = 0
    try:
        service.Disconnect()
        while wait_time < wait_timeout:
            sprops = service.GetProperties()
            state = sprops.get("State", None)
#           print >>sys.stderr, "time %3.1f state %s" % (wait_time, state)
            if state == "idle":
                break
            time.sleep(.5)
            wait_time += .5
    except:
        pass
    print "disconnect in %3.1f secs" % wait_time
    break
sys.exit(0)
