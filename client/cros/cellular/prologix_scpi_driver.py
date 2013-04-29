#!/usr/bin/python
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import select
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

    def __init__(self, hostname, port=1234, gpib_address=14,
                 read_timeout_seconds=30, connect_timeout_seconds=5):
        """Constructs a wrapper for the Prologix TCP<->GPIB bridge :
        Arguments:
            hostname: hostname of prologix device
            port: port number
            gpib_address: initial GPIB device to connect to
            read_timeout_seconds: the read time out for the socket to the
                prologix box
            connect_timeout_seconds: the read time out for the socket to the
                prologix box
        """
        self.scpi_logger = logging.getLogger('prologix')
        self.scpi_logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        s = 'IP:%s GPIB:%s: ' % (hostname, gpib_address)
        formatter = logging.Formatter('%(asctime)s %(filename)s %(lineno)d ' +
                                      s + ' %(name)s - %(message)s')
        ch.setFormatter(formatter)
        # Replaces all handlers with this one. Otherwise, on each creation of
        # this object type, we add one more handler. This setup could be done
        # outside the class, but then it runs at import time. And we need the
        # hostname and GPIB address.
        self.scpi_logger.handlers = [ch]
        # Don't pass this up to other loggers. True here will print duplicates
        # to the log.
        self.scpi_logger.propagate = False

        self.socket = connect_to_port(hostname, port, connect_timeout_seconds)
        self.read_timeout_seconds = read_timeout_seconds
        self.socket.setblocking(0)
        self.SetAuto(1)
        # We may need this later.
        #self._AddCarrigeReturnsToResponses()
        self.SetGpibAddress(gpib_address)
        self.scpi_logger.debug('set read_timeout_seconds: %s ' %
                               self.read_timeout_seconds)

    def __del__(self):
        self.Close()

#   This function is commented for now. The PXT may need to the Prologix
#   adapter to append a newline to each GPIB response.
#   def _AddCarrigeReturnsToResponses(self):
#     """
#     Have the prologix box add a line feed to each response.
#     Some instruments may need this.
#     """
#     pass
#     self.Send('++eot_enable 1')
#     self.Send('++eot_char 10')

    def SetAuto(self, auto):
        """Controls Prologix read-after-write (aka 'auto') mode."""
        # Must be an int so we can send it as an arg to ++auto.
        self.auto = int(auto)
        self.Send('++auto %d' % self.auto)

    def Close(self):
        """Closes the socket."""
        try:
            self.socket.close()
        except AttributeError:  # Maybe we close before we finish building.
            pass

    def SetGpibAddress(self, gpib_address):
        max_tries = 10
        while max_tries > 0:
            max_tries -= 1
            self.Send('++addr %s' % gpib_address)
            read_back_value = self._DirectQuery('++addr')
            try:
                if (int(read_back_value) == int(gpib_address)):
                    break
            except ValueError:
                # If we read a string, don't raise, just try again.
                pass
            self.scpi_logger.error('Set gpib addr to: %s, read back: %s' %
                                   (gpib_address, read_back_value))
            self.scpi_logger.error('Setting the GPIB address failed. ' +
                                   'Trying again...')

    def Send(self, command):
        self.scpi_logger.info('] %s', command)
        try:
            self.socket.send(command + '\n')
        except Exception as e:
            self.scpi_logger.error('sending SCPI command %s failed. ' %
                                   command)
            self.scpi_logger.exception(e)
            raise SystemError('Sending SCPI command failed. ' +
                              'Instrument stopped talking?')

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
        try:
            ready = select.select([self.socket], [], [],
                                  self.read_timeout_seconds)
        except Exception as e:
            self.scpi_logger.exception(e)
            s = 'Read from the instrument failed. Timeout:%s' % \
                self.read_timeout_seconds
            self.scpi_logger.error(s)
            raise SystemError(s)

        if ready[0]:
            response = self.socket.recv(4096)
            response = response.rstrip()
            self.scpi_logger.info('[ %s', response)
            return response
        else:
            self.Close()
            s = 'Connection to the prologix adapter worked.' \
                'But there was not data to read from the instrument.' \
                'Does that command return a result?' \
                'Bad GPIB port number, or timeout too short?'
        raise SystemError(s)

    def Query(self, command):
        """Send a GPIB command and return the response."""
        #self.SetAuto(1) #maybe useful?
        self.Send(command)
        if not self.auto:
            self.Send('++read eoi')
        output = self.Read()
        #self.SetAuto(0) #maybe useful?
        return output

    def _DirectQuery(self, command):
        """Sends a query to the prologix (do not send ++read).

        Returns: response of the query.
        """
        self.Send(command)
        return self.Read()


def connect_to_port(hostname, port, connect_timeout_seconds):
    # Right out of the python documentation,
    #  http://docs.python.org/library/socket.html
    for res in socket.getaddrinfo(
                hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM):
        af, socktype, proto, _, sa = res
        try:
            s = socket.socket(af, socktype, proto)
        except socket.error as msg:
            raise SystemError('Failed to make a new socket object. ' +
                              str(msg))
        try:
            s.settimeout(connect_timeout_seconds)
            s.connect(sa)
        except socket.error as msg:
            try:
                s.close()
            except Exception:
                pass  # Try to close it, but it may not have been created.
            temp_string_var = ' Could be bad IP address. Tried: %s : %s' % \
                              (hostname, port)
            raise SystemError(str(msg) + temp_string_var)
    return s
