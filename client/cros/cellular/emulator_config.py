# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Configure cellular data emulation setup."""
import time

from autotest_lib.client.cros.cellular import base_station_8960, cellular
from autotest_lib.client.cros.cellular import prologix_scpi_driver, scpi


def _ConfigureOneBaseStation(c):
  if c['type'] == '8960-prologix':

    adapter = c['gpib_adapter']

    s = scpi.Scpi(
        prologix_scpi_driver.PrologixScpiDriver(
            hostname=adapter['ip_address'],
            port=adapter['ip_port'],
            gpib_address=adapter['gpib_address']))
    bs = base_station_8960.BaseStation8960(s)

    bs.SetBsNetmaskV4(c['bs_netmask'])
    bs.SetBsIpV4(*c['bs_addresses'])

    bs.SetUeIpV4(*c['ue_rf_addresses'])
    bs.SetUeDnsV4(*c['ue_dns_addresses'])

    return bs

  else:
    raise KeyError('Could not configure basestation of type %s' % c['type'])


def ConfigureBaseStations(config):
  """Extract base stations from supplied dictionary and configure them."""
  return [_ConfigureOneBaseStation(x) for x in config['basestations']]


def GetDefaultBasestation(config, technology):
  """Set up a base station and turn it on.  Return BS and verifier."""
  bs = ConfigureBaseStations(config)[0]

  bs.SetTechnology(technology)
  bs.SetPower(-40)
  verifier = bs.GetAirStateVerifier()
  bs.Start()

  # TODO(rochberg):  Why does this seem to be necessary?
  time.sleep(10)

  return (bs, verifier)
