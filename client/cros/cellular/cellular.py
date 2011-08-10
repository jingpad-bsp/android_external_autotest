# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Constants, enums, and basic types for cellular base station emulation."""

DEFAULT_TIMEOUT = 10


class Technology(object):
  GPRS = 1
  EGPRS = 2
  WCDMA = 3
  UTRAN = WCDMA
  HSDPA = 4
  HDUPA = 5
  HSDUPA = 6
  HSPA_PLUS = 7

  CDMA_2000 = 8
  EVDO_1x = 9

  LTE = 10

class UeStatus(object):
  NONE = 0
  IDLE = 1
  ATTACHING = 2
  DETACHING = 3
  ACTIVE = 4


class Power(object):
  """Useful power levels, in dBm."""
  OFF = -200
  DEFAULT = -35


class SmsAddress(object):
  def __init__(self, address, address_type='INAT', address_plan='ISDN'):
    """Constructs an SMS address.

    For expediency, the address type arguments come from the GPIB
    commands for the Agilent 8960.  See
    http://wireless.agilent.com/rfcomms/refdocs/gsmgprs/gprsla_hpib_sms.html#CIHDGBIH

    Arguments:
      address:  1-10 octets
      address_type:  INAT, NAT, NET, SUBS, ALPH, ABBR, RES
      address_plan:  ISDN, DATA, TEL, SCS1, SCS2, PRIV, NATional, ERMes, RES
      """
    self.address = address
    self.address_type = address_type
    self.address_plan = address_plan

class TestEnvironment(object):
  def __init__(self, event_loop):
    pass

  def RequestBaseStations(self,
                          configuration,
                          requirements_list):
    """Requests a set of base stations that satisfy the given requirements.

    Arguments:
      configuration:  configuration dictionary
      requirements_list: A list of lists of technologies that must be
        supported

    Returns: a list of base stations.
    """
    pass

  def TimedOut(self):
    """Called by base stations when an expected event hasn't occurred."""
    pass
