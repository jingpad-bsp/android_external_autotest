# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import collections
from signal import SIGHUP
from signal import SIGTERM
import unittest

import mock
from mock import sentinel

from lucifer import sigtrap


class SigtrapTestCase(unittest.TestCase):
    """run_event_command() unit tests."""

    def setUp(self):
        super(SigtrapTestCase, self).setUp()
        self.signal = _FakeSignal(sentinel.default_handler)
        patch = mock.patch('signal.signal', self.signal)
        patch.start()
        self.addCleanup(patch.stop)

    def test_handle_signal(self):
        """Test handle_signal."""
        handlers = self.signal.handlers
        with sigtrap.handle_signal(SIGTERM, sentinel.new):
            self.assertEqual(handlers[SIGTERM], sentinel.new)
        self.assertEqual(handlers[SIGTERM], sentinel.default_handler)

    def test_handle_signals(self):
        """Test handle_signals."""
        handlers = self.signal.handlers
        with sigtrap.handle_signals([SIGTERM, SIGHUP],
                                    sentinel.new):
            self.assertEqual(handlers[SIGTERM], sentinel.new)
            self.assertEqual(handlers[SIGHUP], sentinel.new)
        self.assertEqual(handlers[SIGTERM], sentinel.default_handler)
        self.assertEqual(handlers[SIGHUP], sentinel.default_handler)


class _FakeSignal(object):
    """Fake for signal.signal()"""

    def __init__(self, handler):
        self.handlers = collections.defaultdict(lambda: handler)

    def __call__(self, signum, handler):
        old = self.handlers[signum]
        self.handlers[signum] = handler
        return old
