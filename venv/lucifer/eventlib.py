# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Status change events module.

This is used to standardize communication of events between processes
through a pipe, generally through stdout.

run_event_command() starts a process that sends such events to stdout
and handles them through a callback.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging
import os
from signal import SIGHUP
from signal import SIGINT
from signal import SIGTERM

import enum
import subprocess32

from lucifer import sigtrap

logger = logging.getLogger(__name__)


class Event(enum.Enum):
    """Status change event enum

    Members of this enum represent all possible status change events
    that can be emitted by an event command and that need to be handled
    by the caller.

    The value of enum members must be a string, which is printed by
    itself on a line to signal the event.

    This should be backward compatible with all versions of
    job_shepherd, which lives in the infra/lucifer repository.
    """
    STARTING = 'starting'
    COMPLETED = 'completed'


def run_event_command(event_handler, args, logfile):
    """Run a command that emits events.

    Events printed by the command will be handled by event_handler.
    While the process for the command is running, trapped signals will
    be passed on to it so it can abort gracefully.

    @param event_handler: callable that takes an Event instance.
    @param args: passed to subprocess.Popen.
    @param logfile: file to store stderr.  Must be associated
                    with a file descriptor.
    """
    logger.debug('Starting event command with %r', args)
    with open(os.devnull, 'w+') as devnull, \
         sigtrap.handle_signal(SIGHUP, lambda s, f: None), \
         subprocess32.Popen(args,
                            stdin=devnull,
                            stdout=subprocess32.PIPE,
                            stderr=logfile) as proc, \
         sigtrap.handle_signals([SIGINT, SIGTERM],
                                lambda s, f: os.kill(proc.pid, s)):
        _handle_subprocess_events(event_handler, proc)
    logger.debug('Subprocess exited with %d', proc.returncode)
    return proc.returncode


def _handle_subprocess_events(event_handler, proc):
    """Handle a subprocess that emits events.

    Events printed by the subprocess will be handled by event_handler.

    @param event_handler: callable that takes an Event instance.
    @param proc: Popen instance.
    """
    while True:
        logger.debug('Reading subprocess stdout')
        line = proc.stdout.readline()
        if line:
            _handle_output_line(event_handler, line)
        else:
            break


def _handle_output_line(event_handler, line):
    """Handle a line of output from an event subprocess.

    @param event_handler: callable that takes a StatusChangeEvent.
    @param line: line of output.
    """
    try:
        event = Event(line.rstrip())
    except ValueError:
        logger.warning('Invalid output %r received', line)
    else:
        event_handler(event)
