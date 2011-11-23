# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re
import time

import air_state_verifier
import base_station_interface
import cellular


class Error(Exception):
  pass


class Timeout(Error):
  pass


POLL_SLEEP=0.2


class BaseStation8960(base_station_interface.BaseStationInterface):
  """Wrap an Agilent 8960 Series 10."""

  def __init__(self,
               scpi_connection):
    self.c = scpi_connection
    self._Verify()
    self._Reset()
    self.SetPower(cellular.Power.DEFAULT)

  def _Verify(self):
    idn = self.c.Query('*IDN?')
    if '8960 Series 10 E5515C' not in idn:
      raise Error('Not actually an 8960:  *IDN? says ' + idn)

  def _Reset(self):
    logging.info('Clearing out old errors')
    self.c.RetrieveErrors()
    self.c.Reset()
    self.c.WaitAndCheckError()
    self.Stop()

  def GetAirStateVerifier(self):
    return air_state_verifier.AirStateVerifierBasestation(self)

  def GetDataCounters(self):
    output = {}
    for counter in ['OTATx', 'OTARx', 'IPTX', 'IPRX']:
      result_text = self.c.Query('CALL:COUNT:DTMonitor:%s:DRATe?' % counter)
      result = [float(x) for x in result_text.rstrip().split(',')]
      output[counter] = dict(zip(['Mean', 'Current', 'Max', 'Total'], result))
    logging.info('Data counters: %s', output)
    return output

  def GetUeDataStatus(self):
    status = self.c.Query('CALL:STATus:DATa?')
    return ConfigDictionaries.CALL_STATUS_DATA_TO_STATUS[status]

  def ResetDataCounters(self):
    self.c.SendStanza(['CALL:COUNt:DTMonitor:CLEar'])

  def LogStats(self):
    self.c.Query("CALL:HSDPa:SERVice:PSData:HSDSchannel:CONFig?")

    # Category reported by UE
    self.c.Query("CALL:HSDPa:MS:REPorted:HSDSChannel:CATegory?")
    # The category in use
    self.c.Query("CALL:STATUS:MS:HSDSChannel:CATegory?")
    self.c.Query("CALL:HSDPA:SERV:PSD:CQI?")

  def SetBsIpV4(self, ip1, ip2):
    self.c.SendStanza([
        'SYSTem:COMMunicate:LAN:SELF:ADDRess:IP4 "%s"' % ip1,
        'SYSTem:COMMunicate:LAN:SELF:ADDRess2:IP4 "%s"' % ip2,])

  def SetBsNetmaskV4(self, netmask):
    self.c.SendStanza([
        'SYSTem:COMMunicate:LAN:SELF:SMASk:IP4 "%s"' % netmask,])

  def SetPlmn(self, mcc, mnc):
    # Doing this appears to set the WCDMa versions as well
    self.c.SendStanza([
        'CALL:MCCode %s' % mcc,
        'CALL:MNCode %s' % mnc,])

  def SetPower(self, dbm):
    if dbm <= cellular.Power.OFF :
      self.c.SendStanza([
          'CALL:CELL:POWer:STATe off',])
    else:
      self.c.SendStanza([
          'CALL:CELL:POWer %s' % dbm,])

  def SetTechnology(self, technology):
    #  TODO(rochberg): Check that we're not already in chosen tech for
    #  speed boost
    self.c.SimpleVerify('SYSTem:APPLication:FORMat',
                        ConfigDictionaries.TECHNOLOGY_TO_FORMAT[technology])
    self.c.SendStanza(
        ConfigDictionaries.TECHNOLOGY_TO_CONFIG_STANZA.get(technology, []))
    self.technology = technology

  def SetUeDnsV4(self, dns1, dns2):
    """Set the DNS values provided to the UE.  Emulator must be stopped."""
    stanza = ['CALL:MS:DNSServer:PRIMary:IP:ADDRess "%s"' % dns1]
    if dns2:
      stanza.append('CALL:MS:DNSServer:SECondary:IP:ADDRess "%s"' % dns2)
    self.c.SendStanza(stanza)

  def SetUeIpV4(self, ip1, ip2=None):
    """Set the IP addresses provided to the UE.  Emulator must be stopped."""
    stanza = ['CALL:MS:IP:ADDRess1 "%s"' % ip1]
    if ip2:
      stanza.append('CALL:MS:IP:ADDRess2 "%s"' % ip2)
    self.c.SendStanza(stanza)

  def Start(self):
    self.c.SendStanza(['CALL:OPERating:MODE CALL'])

  def Stop(self):
    self.c.SendStanza(['CALL:OPERating:MODE OFF'])

  def SupportedTechnologies(self):
    return [
      cellular.Technology.GPRS,
      cellular.Technology.EGPRS,
      cellular.Technology.WCDMA,
      cellular.Technology.HSDPA,
      cellular.Technology.HDUPA,
      cellular.Technology.HSDUPA,
      cellular.Technology.HSPA_PLUS,
      cellular.Technology.CDMA_2000,
      cellular.Technology.EVDO_1x,
      ]

  def WaitForStatusChange(self,
                          interested=None,
                          timeout=cellular.DEFAULT_TIMEOUT):
    """When UE status changes (to a value in interested), return the value.

    Arguments:
        interested: if non-None, only transitions to these states will
          cause a return
        timeout: in seconds.
    Returns: state
    Raises:  Error.Timeout
    """
    start = time.time()
    while time.time() - start <= timeout:
      state = self.GetUeDataStatus()
      if state in interested:
        return state
      time.sleep(POLL_SLEEP)

    state = self.GetUeDataStatus()
    if state in interested:
      return state

    raise Timeout('Timed out waiting for state in %s.  State was %s' %
                  (interested, state))

def _Parse(command_sequence):
  """Split and remove comments from a config stanza."""
  uncommented = [re.sub(r'\s*#.*', '', line)
          for line in command_sequence.split('\n')]

  # Return only nonempty lines
  return [line for line in uncommented if line]


class ConfigStanzas(object):
  # p 22 of http://cp.literature.agilent.com/litweb/pdf/5989-5932EN.pdf
  WCDMA_MAX = _Parse("""
# RAB3: 64 Up/384 down
# http://wireless.agilent.com/rfcomms/refdocs/wcdma/wcdmala_hpib_call_service.html#CACBDEAH
CALL:UPLink:TXPower:LEVel:MAXimum 24
CALL:SERVICE:GPRS:RAB GPRSRAB3
""")

  # /home/rochberg/Downloads/USB306PA 14-6-MaxRateHSPA+-1.xml
  CAT_14 = _Parse("""
# Need to figure out whether to remove these lines
system:log:ui:clear
system:log:ui:gpib:state on

call:oper:mode OFF
call:pow:ampl -50;stat ON
call:ms:pow:targ -25
call:cell:rlc:rees OFF
call:hsdp:ms:hsds:cat:cont:auto ON
call:pich:ccode:code 2
call:aich:ccode:code 3
call:ccpchannel:secondary:connected:config:state off
call:ccpchannel:secondary:ccode:code 2
call:dpchannel:ksps15:code:hsdpa 14
call:dpchannel:ksps30:code:hsdpa 4
call:ehichannel:ccode:code 6
call:eagchannel:ccode:code 15
call:hsscchannel1:config:state on
call:hsscchannel2:config:state on
call:hsscchannel3:config:state off
call:hsscchannel4:config:state off
call:hsscchannel1:ccode:code 2
call:hsscchannel2:ccode:code 3
call:hsdpa:service:rbtest:hspdschannel:ccode:code 1
call:hsdpa:service:psdata:hspdschannel:ccode:code 1
call:ocnsource:config:state:hsdpa 1,0,0,0,0,0
call:ocnsource:ccode:code:hsdpa 5,123,124,125,126,127
call:connected:cpichannel:hsdpa -10
call:connected:ccpchannel:primary:state:hsdpa off
call:connected:pichannel:state:hsdpa off
call:connected:dpchannel:hsdpa -20
call:connected:hsscchannel1 -10
call:connected:hsscchannel2 -20
call:connected:hspdschannel -1.5
call:connected:ccpchannel:primary:state:hspa off
call:connected:pichannel:state:hspa off
call:connected:eagchannel -30
call:connected:hsscchannel2:hspa -20
call:connected:hspdschannel:hspa -1.8
call:dpch:ksps15:code 14
call:dpch:ksps30:code 7
call:serv:rbt:rab HSDP12
call:hsdp:serv:rbt:hsds:conf UDEF
call:hsdpa:service:rbtest:udefined:hsdschannel:mac ehspeed
call:hsdpa:service:rbtest:udefined:qam64:state on
call:hsdpa:service:rbtest:udefined:hspdschannel:count 15
call:hsdpa:service:rbtest:udefined:tbsize:index 62
call:hsdpa:service:rbtest:udefined:modulation qam64
call:hsdpa:service:rbtest:udefined:macehs:rlc:sdu 656
call:hsdpa:service:rbtest:udefined:itti 1
call:hsdpa:service:rbtest:udefined:harq:process:count 6
call:hsdpa:service:psdata:hsdschannel:mac ehspeed
call:hsdpa:service:psdata:qam64:state on
call:hsdpa:service:psdata:rlc:downlink:mode flexible
call:hsdpa:service:psdata:rlc:down:max:pdu:psize 1503
call:hsdpa:service:psdata:hsdschannel:config udefined
call:hsdpa:service:psdata:udefined:hspdschannel:count 15
call:hsdpa:service:psdata:udefined:tbsize:index 62
call:hsdpa:service:psdata:udefined:modulation qam64
call:hsdpa:service:psdata:macd:pdusize:control manual
call:hsdpa:service:psdata:macd:pdusize:manual 4816
call:hsdp:serv:psd:cqi 30
call:serv:gprs:rab PHSP
call:conn:cpic:lev:hspa -15;:call:conn:cpic:stat:hspa ON
call:conn:ccpc:sec:lev:hspa -20;:call:conn:ccpc:sec:stat:hspa OFF
call:conn:ccpc:prim:lev:hspa -15;:call:conn:ccpc:prim:stat:hspa ON
call:conn:pich:lev:hspa -15.00;:call:conn:pich:stat:hspa ON
call:conn:dpch:lev:hspa -15;:call:conn:dpch:stat:hspa ON
call:conn:hssc1:lev:hspa -15;:call:conn:hssc1:stat:hspa ON
call:conn:hssc2:lev:hspa -20;:call:conn:hssc2:stat:hspa ON
call:conn:hssc3:lev:hspa -15;:call:conn:hssc3:stat:hspa OFF
call:conn:hssc4:lev:hspa -15;:call:conn:hssc4:stat:hspa OFF
call:conn:hspd:lev:hspa -1.0;:call:conn:hspd:stat:hspa ON
call:conn:ergc:lev:hspa -20.00;:call:conn:ergc:stat:hspa ON
call:serv:psd:srb:mapp UEDD
call:hsup:serv:psd:edpd:ccod:max T2T4
call:hsup:edch:tti MS2
call:hsup:serv:psd:ergc:inf:stat Off
call:oper:mode CALL
CALL:SMS:HTTP:INPUT ON;OUTPUT OFF
CALL:SMS:PTP:MOR:QUE ON
call:hsdpa:service:psdata:hsdschannel:config cqivalue
""")


class ConfigDictionaries(object):
  TECHNOLOGY_TO_FORMAT_RAW = {
      cellular.Technology.GPRS: 'GSM/GPRS',
      cellular.Technology.EGPRS: 'GSM/GPRS',

      cellular.Technology.WCDMA: 'WCDMA',
      cellular.Technology.HSDPA: 'WCDMA',
      cellular.Technology.HDUPA: 'WCDMA',
      cellular.Technology.HSDUPA: 'WCDMA',
      cellular.Technology.HSPA_PLUS: 'WCDMA',

      cellular.Technology.CDMA_2000: 'IS-2000/IS-95/AMPS',

      cellular.Technology.EVDO_1x: 'IS-856',
      }

  # Put each value in "" marks to quote it for GPIB
  TECHNOLOGY_TO_FORMAT = dict([
      (x, '"%s"' % y) for
      x, y in TECHNOLOGY_TO_FORMAT_RAW.iteritems()])

  TECHNOLOGY_TO_CONFIG_STANZA = {
      cellular.Technology.WCDMA: ConfigStanzas.WCDMA_MAX,
      cellular.Technology.HSPA_PLUS: ConfigStanzas.CAT_14,
      }

#  http://wireless.agilent.com/rfcomms/refdocs/wcdma/wcdma_gen_call_proc_status.html#CJADGAHG
  CALL_STATUS_DATA_TO_STATUS = {
      'IDLE': cellular.UeStatus.IDLE,
      'ATTG': cellular.UeStatus.ATTACHING,
      'DET': cellular.UeStatus.DETACHING,
      'OFF': cellular.UeStatus.NONE,
      'PDPAG': cellular.UeStatus.ACTIVATING,
      'PDP': cellular.UeStatus.ACTIVE,
      'PDPD': cellular.UeStatus.DEACTIVATING,
      }
