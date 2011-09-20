#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import socket


class PrologixScpiDriver:
  """Wrapper for a Prologix TCP<->GPIB bridge.
  http://prologix.biz/gpib-ethernet-controller.html
  http://prologix.biz/index.php?dispatch=attachments.getfile&attachment_id=1

  Communication is over a plain TCP stream on port 1234.  Commands to
  the bridge are in-band, prefixed with ++.

  Notable instance variables include:

    self.auto: When 1, the bridge automatically addresses the target
      in listen mode.  When 0, we must issue a ++read after every
      query.  As of Aug '11, something between us and the Agilent 8960
      is wrong such that running in auto=0 mode leaves us hanging if
      we issue '*RST;*OPC?'
  """

  def __init__(self, hostname, port=1234, gpib_address=14):
    """Constructs a wrapper for the Prologix TCP<->GPIB bridge :
    Arguments:
        hostname: hostname of prologix device
        port: port number
        gpib_address: initial GPIB device to connect to
    """
    self.socket = connect_to_port(hostname, port)
    self.read_side = os.fdopen(self.socket.fileno(),'r')
    self.SetAuto(1)
    self.SetGpibAddress(gpib_address)

  def __del__(self):
    self.Close()

  def SetAuto(self, auto):
    """Controls Prologix read-after-write (aka 'auto') mode."""
    self.auto = int(auto)       # Must be an int so we can send it as
                                # an arg to ++auto
    self.Send('++auto %d' % self.auto)

  def Close(self):
    """Close the read_side file and read/write socket in the correct order."""
    if self.read_side: self.read_side.close()
    if self.socket: self.socket.close()

  def SetGpibAddress(self, gpib_address):
    self.Send('++addr %s' % gpib_address)
    actual_gpib_address = self._DirectQuery('++addr')
    assert(int(actual_gpib_address) == int(gpib_address))

  def Send(self, command):
    self.socket.send(command + '\n')

  def Reset(self):
    """Sends a standard SCPI reset and waits for it to complete."""
    # There is some misinteraction between the devices such that if we
    # send *RST and *OPC? and then manually query with ++read,
    # occasionally that ++read doesn't come back.  We currently depend
    # on self.Query to turn on Prologix auto mode to avoid this
    self.Send('*RST')
    self.Query('*OPC?')

  def Read(self):
    """Read a response from the bridge."""
    response = self.read_side.readline()
    if response == '':
      return None
    response = response.rstrip()
    return response

  def Query(self, command):
    """Send a GPIB command and return the response."""
    self.SetAuto(1)
    self.Send(command)
    if not self.auto:
      self.Send('++read eoi')
    output = self.Read()
    self.SetAuto(0)
    return output

  def _DirectQuery(self, command):
    """Sends a query to the prologix (do not send ++read), return response."""
    self.Send(command)
    return self.Read()


def connect_to_port(hostname, port):
  # Right out of the python documentation,
  #  http://docs.python.org/library/socket.html
  for res in socket.getaddrinfo(
    hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM):
    af, socktype, proto, canonname, sa = res
    try:
      s = socket.socket(af, socktype, proto)
    except socket.error, msg:
      s = None
      continue
    try:
      s.connect(sa)
    except socket.error, msg:
      s.close()
      s = None
      continue
    break
  return s
