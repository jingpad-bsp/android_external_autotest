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
from signal import SIGUSR1
from signal import SIG_IGN

import enum
import subprocess32
from subprocess32 import PIPE

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


class Command(enum.Enum):
    """Command enum

    Members of this enum represent all possible command
    that can be sent to an event command.

    The value of enum members must be a string, which is printed by
    itself on a line to signal the event.

    This should be backward compatible with all versions of
    job_shepherd, which lives in the infra/lucifer repository.

    This should only contain one command, ABORT.
    """
    ABORT = 'abort'


def run_event_command(event_handler, args):
    """Run a command that emits events.

    Events printed by the command will be handled by event_handler.
    While the process for the command is running, trapped signals will
    be passed on to it so it can abort gracefully.

    @param event_handler: callable that takes an Event instance.
    @param args: passed to subprocess.Popen.
    """
    logger.debug('Starting event command with %r', args)

    def abort_handler(_signum, _frame):
        """Handle SIGUSR1 by sending abort to subprocess."""
        _send_command(proc.stdin, Command.ABORT)

    with sigtrap.handle_signal(SIGUSR1, SIG_IGN), \
         subprocess32.Popen(args, stdin=PIPE, stdout=PIPE) as proc, \
         sigtrap.handle_signal(SIGUSR1, abort_handler):
        _handle_subprocess_events(event_handler, proc)
    logger.debug('Subprocess exited with %d', proc.returncode)
    return proc.returncode


def _send_command(f, command):
    """Send a command.

    f is a pipe file object.  command is a Command instance.
    """
    f.write('%s\n' % command.value)
    f.flush()


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
