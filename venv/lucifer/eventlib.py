# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Event subprocess module.

Event subprocesses are subprocesses that print event changes to stdout.

Each event is a UNIX line, with a terminating newline character.

run_event_command() starts such a process with a synchronous event handler.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging

import enum
import subprocess32
from subprocess32 import PIPE

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
    PARSING = 'parsing'
    COMPLETED = 'completed'


def run_event_command(event_handler, args):
    """Run a command that emits events.

    Events printed by the command will be handled by event_handler
    synchronously.  Exceptions raised by event_handler will not be
    caught.  If an exception escapes, the child process's standard file
    descriptors are closed and the process is waited for.  The
    event command should terminate if this happens.

    @param event_handler: callable that takes an Event instance.
    @param args: passed to subprocess.Popen.
    """
    logger.debug('Starting event command with %r', args)
    with subprocess32.Popen(args, stdout=PIPE) as proc:
        logger.debug('Event command child pid is %d', proc.pid)
        _handle_subprocess_events(event_handler, proc)
    logger.debug('Event command child with pid %d exited with %d',
                 proc.pid, proc.returncode)
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
        if not line:
            break
        _handle_output_line(event_handler, line)


def _handle_output_line(event_handler, line):
    """Handle a line of output from an event subprocess.

    @param event_handler: callable that takes a StatusChangeEvent.
    @param line: line of output.
    """
    try:
        event = Event(line.rstrip())
    except ValueError:
        logger.warning('Invalid output %r received', line)
        return
    event_handler(event)
