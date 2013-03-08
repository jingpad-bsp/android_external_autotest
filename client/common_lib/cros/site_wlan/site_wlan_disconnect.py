#!/usr/bin/python

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import array
# Once these are no longer copied to DUTs manually, this should become
# from autotest_lib.client.common_lib.cros.site_wlan import constants
import constants
import dbus
import sys
import time

from site_wlan_dbus_setup import *

def disconnect_wait(service, wait_timeout):
  wait_time = 0
  try:
    service.Disconnect()
    while wait_time < wait_timeout:
      sprops = service.GetProperties()
      state = sprops.get("State", None)
      if state == "idle":
        break
      time.sleep(.5)
      wait_time += .5
  except:
    pass
  print "disconnect in %3.1f secs" % wait_time

def main(argv):
  target_ssid = sys.argv[1]
  wait_timeout = int(sys.argv[2])
  should_disconnect = False

  mprops = manager.GetProperties()
  for path in mprops["Services"]:
    service = dbus.Interface(bus.get_object(constants.CONNECTION_MANAGER, path),
      constants.CONNECTION_MANAGER_SERVICE)
    sprops = service.GetProperties()

    # If the service's SSID contains unprintable characters then this property
    #  'WiFi.HexSSID' is present and holds a hex-encoded copy of the SSID.
    # Otherwise, 'WiFi.HexSSID' is None.
    # Convert 'dbus.String' to 'str' for comparison.
    ssid = str(sprops.get("Name", None))
    hex_ssid = str(sprops.get("WiFi.HexSSID", None))
    target_hex_ssid = target_ssid.encode("hex").upper()

    if ssid == target_ssid:
      should_disconnect = True
    elif (hex_ssid is not None) and (hex_ssid == target_hex_ssid):
      should_disconnect = True

    if should_disconnect:
      disconnect_wait(service, wait_timeout)
      break

  sys.exit(0)

if __name__ == '__main__':
  main(sys.argv)
