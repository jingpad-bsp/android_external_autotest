# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class SCPI:
  """Standard commands for programmable instruments, often called GPIB commands.
  """
  def Send(self, command, callback=None, address=None):
    """Sends the specified command.  Does not wait for a response."""
    pass

  def Query(self, command, callback=None, address=None):
    """Sends the specified command, waits for a response, and returns it."""
    pass

DEFAULT_TIMEOUT = 10

class Technology:
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

class UeStatus:
  NONE = 0
  IDLE = 1
  ATTACHING = 2
  DETACHING = 3
  ACTIVE = 4


class Power:
  """Useful power levels, in dBm."""
  OFF = -200
  DEFAULT = -35


class SmsAddress:
  def __init__(self, address, address_type='INAT', address_plan='ISDN'):
    """Constructs an SMS address.

    For expediency, the address type arguments come from the GPIB
    commands for the Agilent 8960.
       See http://wireless.agilent.com/rfcomms/refdocs/gsmgprs/gprsla_hpib_sms.html#CIHDGBIH

    Arguments:
      address:  1-10 octets
      address_type:  INAT, NAT, NET, SUBS, ALPH, ABBR, RES
      address_plan:  ISDN, DATA, TEL, SCS1, SCS2, PRIV, NATional, ERMes, RES
      """
    self.address = address
    self.address_type = address_type
    self.address_plan = address_plan


class TestEnvironment(self):
  def __init__(self, event_loop):
    pass

  def RequestBaseStations(self,
                          requirements_list):
    """Requests a set of base stations that satisfy the given requirements.
    Arguments:
      requirements_list: A list of lists of technologies that must be
        supported
    Returns:
       a list of base stations.
       """
    pass

  def TimedOut(self):
    """Called by base stations when an expected event hasn't occurred."""
    pass

class BaseStation:
  def __init__(self, test_environment, technology):
    """Creates a base station of the specified technology."""
    pass

  def Start(self):
    pass

  def Stop(self):
    pass

  def SetFrequencyBand(self, band):
    """Sets the frequency used by the BSS.  BSS must be stopped.

    Arguments:
      band:  A band number, from the UMTS bands summarized at
        http://en.wikipedia.org/wiki/UMTS_frequency_bands
        Use band 5 for 800MHz C2k/EV-DO,  2 for 1900MHz C2k/EV-DO
    """
    pass

  def SetPlmn(self, mcc, mnc):
    """Sets the mobile country and network codes.  BSS must be stopped."""
    pass

  def SetPower(self, dBm):
    """Sets the output power of the base station.
    Arguments:
      dBm:  Power, in dBm.  See class Power for useful constants.
    """
    pass

  def GetUeStatus(self):
    """Gets the status of the UE."""
    pass

  # Unresolved:
  #   Are ExpectXxx calls a one-shot?
  #   Do we even want to investigate python coroutines?

  def ExpectUeStatusChange(self,
                           callback,
                           interested=None,
                           timeout=DEFAULT_TIMEOUT,
                           **kwargs):
    """When UE status changes (to a value in interested), call back.
    Arguments:
        callback: called with (self, new_status, **kwargs).
        timeout_callback:  called with (self, **kwargs).  Default:
        interested: if non-None, only transitions to these states will
          cause a callback
        timeout: in seconds
        kwargs:  Passed to callback. """
    pass

  def ExpectSmsReceived(self,
                        callback,
                        timeout=DEFAULT_TIMEOUT,
                        **kwargs):
    """Call callback when SMS is received from the UE.
    Arguments:
      callback:  called with (self, message, **kwargs).
      timeout:  in seconds.  parent test environment is notified.
      """
    pass

  def SendSms(self,
              message,
              OAddress=SmsAddress('8960')
              Dcs=0xf0):
    """Sends the supplied SMS message."""
    pass


class GsmBaseStation
  def SetCategory(self, category):
    """Sets the UMTS category for a device."""
    pass
