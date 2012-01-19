#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


'''
SCPI-over-TCP controller.
'''


import logging
import signal
import socket
from contextlib import contextmanager

class Error(Exception):
    pass


@contextmanager
def Timeout(secs):
    def handler(signum, frame):
        raise Error('Timeout')

    if secs:
        if signal.alarm(secs):
            raise Error('Alarm was already set')

    signal.signal(signal.SIGALRM, handler)

    try:
        yield
    finally:
        if secs:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, lambda signum, frame: None)


class LanScpi(object):
    '''A SCPI-over-TCP controller.'''
    def __init__(self, host, port=5025, timeout=60):
        '''
        Connects to a device using SCPI-over-TCP.

        @param host: Host to connect to.
        @param port: Port to connect to.
        @param timeout: Timeout in seconds.  (Uses the ALRM signal.)
        '''
        self.timeout = timeout
        self.logger = logging.getLogger('SCPI')
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        with Timeout(self.timeout):
            self.logger.info('] Connecting to %s:%d...' % (
                    host, port))
            self.socket.connect((host, port))

        self.rfile = self.socket.makefile('rb', -1)  # Default buffering
        self.wfile = self.socket.makefile('wb', 0)   # No buffering

        self.logger.info('Connected')

        self.id = self.Query('*IDN?')


    def Send(self, commands, wait=True):
        '''
        Sends a command or series of commands.

        @param commands: The commands to send.  May be list, or a string if
            just a single command.
        @param wait: If True, issues an *OPC? command after the final
            command to block until all commands have completed.
        '''
        if type(commands) == str:
            self.Send([commands], wait)
            return

        self._WriteLine('*CLS')
        for command in commands:
            if command[-1] == '?':
                raise Error('Called Send with query %r' % command)
            self._WriteLine(command)
            self._WriteLine('SYST:ERR?')

        errors = []
        for i in range(len(commands)):
            ret = self._ReadLine()
            if ret != '+0,"No error"':
                errors.append(
                    'Issuing command %r: %r' % (commands[i], ret))
        if errors:
            raise Error('; '.join(errors))

        if wait:
            self._WriteLine('*OPC?')
            ret = self._ReadLine()
            if ret not in ['1','+1']:
                raise Error('Expected 1 after *OPC? but got %r' % ret)

    def Query(self, command, format=None):
        '''
        Issues a query, returning the result.
        '''
        if command[-1] != '?':
            raise Error('Called Query with non-query %r' % command)
        self._WriteLine('*CLS')
        self._WriteLine(command)
        self._WriteLine('*ESR?')
        self._WriteLine('SYST:ERR?')
        line1 = self._ReadLine()
        line2 = self._ReadLine()
        # On success, line1 is the queried value and line2 is the status
        # register.  On failure, line1 is the status register and line2
        # is the error string.  We do this to make sure that we can
        # detect an unknown header rather than just waiting forever.
        if ',' in line2:
            raise Error('Error issuing command %r: %r' % (command, line2))

        # Success!  Get SYST:ERR, which should be +0
        line3 = self._ReadLine()
        if line3 != '+0,"No error"':
            raise Error('Error issuing command %r: %r' % (command, line3))

        if format:
            line1 = format(line1)
        return line1

    def Quote(self, string):
        '''
        Quotes a string.
        '''
        # TODO(jsalz): Use the real IEEE 488.2 string format.
        return '"%s"' % string

    def _ReadLine(self):
        '''
        Reads a single line, timing out in self.timeout seconds.
        '''

        with Timeout(self.timeout):
            if not self.timeout:
                self.logger.info('[ (waiting)')
            ret = self.rfile.readline().rstrip('\n')
            self.logger.info('[ %s' % ret)
            return ret

    def _WriteLine(self, command):
        '''
        Writes a single line.
        '''
        if '\n' in command:
            raise Error('Newline in command: %r' % command)
        self.logger.info('] %s' % command)
        print >>self.wfile, command


# Formats.
FLOATS = lambda s: [float(f) for f in s.split(",")]
