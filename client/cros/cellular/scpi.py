#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging


class Error(Exception):
  pass


class Scpi(object):
  """Wrapper for SCPI.

  SCPI = "standard commands for programmable instruments",
  a relative of GPIB.

  The SCPI driver must export:  Send, Query, and Reset
  """

  def __init__(self, driver, opc_on_stanza=False):
    self.driver = driver
    self.opc_on_stanza = opc_on_stanza
    self.scpi_logger = logging.getLogger('SCPI')

  def Query(self, command):
    """Send the SCPI command and return the response."""
    self.scpi_logger.info('] %s', command)
    response = self.driver.Query(command)
    self.scpi_logger.info('[ %s', response)
    return response

  def Send(self, command):
    """Send the SCPI command."""
    self.scpi_logger.info('] %s', command)
    self.driver.Send(command)

  def Reset(self):
    """Tell the device to reset with *RST."""
    # Some devices (like the prologix) require special handling for
    # reset.
    self.driver.Reset()

  def RetrieveErrors(self):
    """Retrieves all SYSTem:ERRor messages from the device."""
    errors = []
    while True:
      error = self.Query('SYSTem:ERRor?')
      if '+0,"No error"' in error:
        # We've reached the end of the error stack
        break
      if '-420' in error and 'Query UNTERMINATED' in error:
        # This is benign; the GPIB bridge asked for a response when
        # the device didn't have one to give.

        # TODO(rochberg): This is a layering violation; we should
        # really only accept -420 if the underlying driver is in a
        # mode that is known to cause this
        continue
      else:
        errors.append(error)
    self.Send('*CLS')           # Clear status
    errors.reverse()
    return errors

  def WaitAndCheckError(self):
    """Waits for command completion, checks for errors."""
    self.Query('*OPC?')      # Wait for operation complete
    errors = self.RetrieveErrors()
    if errors:
      raise Error('\n'.join(errors))

  def SimpleVerify(self, command, arg):
    """Sends "command arg", then "command?", expecting arg back.

    Arguments:
      command: SCPI command
      arg: Argument.  We currently check for exact equality: you should
        send strings quoted with " because that's what the 8960 returns.
        We also fail if you send 1 and receive +1 back.

    Raises:
      Error:  Verification failed
    """
    self.Send('%s %s' % (command, arg))
    self.WaitAndCheckError()
    result = self.Query('%s?' % (command,))
    if result != arg:
      raise Error('Error on %s: sent %s, got %s' % (command, arg, result))

  def SendStanza(self, commands):
    """Sends a list of commands, checks to see that they complete correctly."""
    self.WaitAndCheckError()

    for c in commands:
      if self.opc_on_stanza:
        self.Query(c + ';*OPC?')
      else:
        self.Send(c)

    self.WaitAndCheckError()
