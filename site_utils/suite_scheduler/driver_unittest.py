#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for site_utils/board_enumerator.py."""

import logging
import mox
import unittest

import driver, timed_event, board_enumerator

from autotest_lib.server import frontend


class DriverTest(mox.MoxTestBase):
    """Unit tests for Driver."""


    def setUp(self):
        super(DriverTest, self).setUp()
        self.afe = self.mox.CreateMock(frontend.AFE)
        self.nightly = self.mox.CreateMock(timed_event.Nightly)
        self.weekly = self.mox.CreateMock(timed_event.Weekly)

        self.mox.StubOutWithMock(timed_event.Nightly, 'CreateFromConfig')
        self.mox.StubOutWithMock(timed_event.Weekly, 'CreateFromConfig')
        timed_event.Nightly.CreateFromConfig(
            mox.IgnoreArg(),
            mox.IgnoreArg()).AndReturn(self.nightly)
        timed_event.Weekly.CreateFromConfig(
            mox.IgnoreArg(),
            mox.IgnoreArg()).AndReturn(self.weekly)
        self.mox.ReplayAll()

        self.driver = driver.Driver(afe=self.afe, config=None)
        self.mox.VerifyAll()
        self.mox.ResetAll()


    def _ExpectEnumeration(self):
        """Expect one call to PlatformEnumerator.Enumerate()."""
        prefix = board_enumerator.PlatformEnumerator._LABEL_PREFIX
        mock = self.mox.CreateMock(frontend.Label)
        mock.name = prefix + 'supported-board'
        self.afe.get_labels(name__startswith=prefix).AndReturn([mock])


    def testHandleAllEventsOnce(self):
        """Test that all events being ready is handled correctly."""
        self._ExpectEnumeration()
        self.nightly.ShouldHandle().InAnyOrder('events').AndReturn(True)
        self.nightly.Handle(mox.IgnoreArg()).InAnyOrder('events')
        self.weekly.ShouldHandle().InAnyOrder('events').AndReturn(True)
        self.weekly.Handle(mox.IgnoreArg()).InAnyOrder('events')
        self.mox.ReplayAll()

        self.driver.HandleEventsOnce()


    def testHandleNightlyEventOnce(self):
        """Test that one ready event is handled correctly."""
        self._ExpectEnumeration()
        self.weekly.ShouldHandle().InAnyOrder('events').AndReturn(False)
        self.nightly.ShouldHandle().InAnyOrder('events').AndReturn(True)
        self.nightly.Handle(mox.IgnoreArg()).InAnyOrder('events')
        self.mox.ReplayAll()

        self.driver.HandleEventsOnce()


if __name__ == '__main__':
    unittest.main()
