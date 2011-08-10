# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re

import base_station_interface
import cellular


class Error(Exception):
  pass


class BaseStation8960(base_station_interface.BaseStationInterface):
  """Wrap an Agilent 8960 Series 10."""

  def __init__(self,
               scpi_connection,
               technology):
    self.c = scpi_connection
    self._Verify()
    self._Reset()
    self.SetTechnology(technology)

  def _Verify(self):
    idn = self.c.Query('*IDN?')
    if '8960 Series 10 E5515C' not in idn:
      raise Error('Not actually an 8960:  *IDN? says ' + idn)

  def _Reset(self):
    logging.info('Clearing out old errors')
    self.c.RetrieveErrors()
    self.c.Send('*RST')
    self.c.Query('*OPC?')
    self.c.WaitAndCheckError()

  def SetTechnology(self, technology):
    self.c.SimpleVerify('SYSTem:APPLication:FORMat',
                        ConfigDictionaries.TECHNOLOGY_TO_FORMAT[technology])
    self.c.SendStanza(
        ConfigDictionaries.TECHNOLOGY_TO_CONFIG_STANZA.get(technology, []))


def _Parse(command_sequence):
  """Split and remove comments from a config stanza."""
  return [re.sub(r'\s*#.*', '', line)
          for line in command_sequence.split('\n')]


class ConfigStanzas(object):
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
      cellular.Technology.UTRAN: 'WCDMA',
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
      cellular.Technology.HSPA_PLUS: ConfigStanzas.CAT_14,
      }
