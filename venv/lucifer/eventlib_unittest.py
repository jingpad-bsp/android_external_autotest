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
import sys
import time

import mock
import pytest
import subprocess32

from lucifer import eventlib
from lucifer.eventlib import Event


@pytest.fixture
def signal_mock():
    """Pytest fixture for mocking out signal handler setting."""
    fake_signal = _FakeSignal(mock.sentinel.default_handler)
    with mock.patch('signal.signal', fake_signal):
        yield fake_signal


def test_happy_path(signal_mock, capfd):
    """Test happy path."""
    handler = _FakeHandler()

    ret = eventlib.run_event_command(
            event_handler=handler,
            args=['bash', '-c',
                  'echo starting;'
                  'echo log message >&2;'
                  'echo completed;'])

    # Handler should be called with events in order.
    assert handler.events == [Event('starting'), Event('completed')]
    # Handler should return the exit status of the command.
    assert ret == 0
    # Signal handler should be restored.
    assert signal_mock.handlers[signal.SIGUSR1] == signal_mock.default_handler
    # stderr should go to stderr.
    out, err = capfd.readouterr()
    assert out == ''
    assert err == 'log message\n'


@pytest.mark.xfail(reason='Flaky due to sleep')
def test_SIGUSR1_aborts():
    """Test sending SIGUSR1 aborts."""
    with subprocess32.Popen(
            [sys.executable, '-m', 'lucifer.scripts.run_event_command',
             sys.executable, '-m', 'lucifer.scripts.wait_for_abort']) as proc:
        time.sleep(0.2)  # Wait for process to come up.
        os.kill(proc.pid, signal.SIGUSR1)
        time.sleep(0.1)
        proc.poll()
        # If this is None, the process failed to abort.  If this is
        # -SIGUSR1 (-10), then the processes did not finish setting up
        # yet.
        assert proc.returncode == 0


class RunEventCommandTestCase(unittest.TestCase):
    """run_event_command() unit tests."""

    def setUp(self):
        super(RunEventCommandTestCase, self).setUp()
        self.signal = _FakeSignal(mock.sentinel.default_handler)
        patch = mock.patch('signal.signal', self.signal)
        patch.start()
        self.addCleanup(patch.stop)

    def test_failed_command(self):
        """Test failed command."""
        handler = _FakeHandler()

        ret = eventlib.run_event_command(
                event_handler=handler,
                args=['bash', '-c', 'exit 1'])

        # Handler should return the exit status of the command.
        self.assertEqual(ret, 1)

    def test_with_invalid_events(self):
        """Test passing invalid events."""
        handler = _FakeHandler()

        eventlib.run_event_command(
                event_handler=handler,
                args=['bash', '-c', 'echo foo; echo bar'])

        # Handler should not be called with invalid events.
        self.assertEqual(handler.events, [])

    def test_should_not_hide_handler_exception(self):
        """Test handler exceptions."""
        handler = _RaisingHandler(_TestError)
        with self.assertRaises(_TestError):
            eventlib.run_event_command(
                    event_handler=handler,
                    args=['bash', '-c', 'echo starting; echo completed'])


class _FakeSignal(object):
    """Fake for signal.signal()"""

    def __init__(self, default_handler):
        self.default_handler = default_handler
        self.handlers = collections.defaultdict(lambda: default_handler)

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
