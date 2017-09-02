# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import collections
import os
import unittest
import signal
import tempfile

import mock

from lucifer import eventlib
from lucifer.eventlib import Event


class RunEventCommandTestCase(unittest.TestCase):
    """run_event_command() unit tests."""

    def setUp(self):
        super(RunEventCommandTestCase, self).setUp()
        self.signal = _FakeSignal(mock.sentinel.default_handler)
        patch = mock.patch('signal.signal', self.signal)
        patch.start()
        self.addCleanup(patch.stop)

    def test_happy_path(self):
        """Test happy path."""
        handler = _FakeHandler()

        with tempfile.TemporaryFile() as logfile:
            ret = eventlib.run_event_command(
                    event_handler=handler,
                    args=['bash', '-c',
                          'echo starting;'
                          'echo log message >&2;'
                          'echo completed;'],
                    logfile=logfile)

            # Handler should be called with events in order.
            self.assertEqual(handler.events,
                             [Event('starting'), Event('completed')])
            # Handler should return the exit status of the command.
            self.assertEqual(ret, 0)
            # Signal handler should be restored.
            self.assertEqual(self.signal.handlers[signal.SIGINT],
                             mock.sentinel.default_handler)
            self.assertEqual(self.signal.handlers[signal.SIGTERM],
                             mock.sentinel.default_handler)
            self.assertEqual(self.signal.handlers[signal.SIGHUP],
                             mock.sentinel.default_handler)
            # stderr should go to the logfile.
            logfile.seek(0)
            self.assertEqual(logfile.read(), 'log message\n')

    def test_failed_command(self):
        """Test failed command."""
        handler = _FakeHandler()

        with open(os.devnull, 'w') as devnull:
            ret = eventlib.run_event_command(
                    event_handler=handler,
                    args=['bash', '-c', 'exit 1'],
                    logfile=devnull)

        # Handler should return the exit status of the command.
        self.assertEqual(ret, 1)

    def test_with_invalid_events(self):
        """Test passing invalid events."""
        handler = _FakeHandler()

        with open(os.devnull, 'w') as devnull:
            eventlib.run_event_command(
                    event_handler=handler,
                    args=['bash', '-c', 'echo foo; echo bar'],
                    logfile=devnull)

        # Handler should not be called with invalid events.
        self.assertEqual(handler.events, [])

    def test_should_not_hide_handler_exception(self):
        """Test handler exceptions."""
        handler = _RaisingHandler(_TestError)
        with open(os.devnull, 'w') as devnull:
            with self.assertRaises(_TestError):
                eventlib.run_event_command(
                        event_handler=handler,
                        args=['bash', '-c', 'echo starting; echo completed'],
                        logfile=devnull)


class _FakeSignal(object):
    """Fake for signal.signal()"""

    def __init__(self, handler):
        self.handlers = collections.defaultdict(lambda: handler)

    def __call__(self, signum, handler):
        old = self.handlers[signum]
        self.handlers[signum] = handler
        return old


class _FakeHandler(object):
    """Event handler for testing; stores events."""

    def __init__(self):
        self.events = []

    def __call__(self, event):
        self.events.append(event)


class _RaisingHandler(object):
    """Event handler for testing; raises."""

    def __init__(self, exception):
        self._exception = exception

    def __call__(self, event):
        raise self._exception


class _TestError(Exception):
    """Fake exception for tests."""
