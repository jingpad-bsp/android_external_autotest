#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for site_utils/board_enumerator.py."""

import logging, mox,  unittest

import board_enumerator, driver, forgiving_config_parser, manifest_versions
import task, timed_event

from autotest_lib.server import frontend


class DriverTest(mox.MoxTestBase):
    """Unit tests for Driver."""


    def setUp(self):
        super(DriverTest, self).setUp()
        self.afe = self.mox.CreateMock(frontend.AFE)
        self.config = forgiving_config_parser.ForgivingConfigParser()
        self.nightly = self.mox.CreateMock(timed_event.Nightly)
        self.nightly.keyword = timed_event.Nightly.KEYWORD
        self.weekly = self.mox.CreateMock(timed_event.Weekly)
        self.weekly.keyword = timed_event.Weekly.KEYWORD
        self.mv = self.mox.CreateMock(manifest_versions.ManifestVersions)

        self.driver = driver.Driver(afe=self.afe)
        self.driver._mv = self.mv


    def _ExpectSetup(self):
        self.mox.StubOutWithMock(timed_event.Nightly, 'CreateFromConfig')
        self.mox.StubOutWithMock(timed_event.Weekly, 'CreateFromConfig')
        timed_event.Nightly.CreateFromConfig(
            mox.IgnoreArg()).AndReturn(self.nightly)
        timed_event.Weekly.CreateFromConfig(
            mox.IgnoreArg()).AndReturn(self.weekly)


    def _ExpectEnumeration(self):
        """Expect one call to BoardEnumerator.Enumerate()."""
        prefix = board_enumerator.BoardEnumerator._LABEL_PREFIX
        mock = self.mox.CreateMock(frontend.Label)
        mock.name = prefix + 'supported-board'
        self.afe.get_labels(name__startswith=prefix).AndReturn([mock])


    def _ExpectHandle(self, event, group):
        """Make event report that it's handle-able, and expect it to be handle.

        @param event: the mock event that expectations will be set on.
        @param group: group to put new expectations in.
        """
        bbs = {'branch': 'build-string'}
        event.ShouldHandle().InAnyOrder(group).AndReturn(True)
        event.GetBranchBuildsForBoard(mox.IgnoreArg(),
                                      self.mv).InAnyOrder(group).AndReturn(bbs)
        event.Handle(mox.IgnoreArg(), bbs, mox.IgnoreArg()).InAnyOrder(group)


    def testTasksFromConfig(self):
        """Test that we can build a list of Tasks from a config."""
        self.config.add_section(self.nightly.keyword)
        self.config.add_section(self.weekly.keyword)
        self.mox.StubOutWithMock(task.Task, 'CreateFromConfigSection')
        task.Task.CreateFromConfigSection(
            self.config, self.nightly.keyword).InAnyOrder().AndReturn(
                (self.nightly.keyword, self.nightly))
        task.Task.CreateFromConfigSection(
            self.config, self.weekly.keyword).InAnyOrder().AndReturn(
                (self.weekly.keyword, self.weekly))
        self.mox.ReplayAll()
        tasks = self.driver.TasksFromConfig(self.config)
        self.assertTrue(self.nightly in tasks[self.nightly.keyword])
        self.assertTrue(self.weekly in tasks[self.weekly.keyword])


    def testHandleAllEventsOnce(self):
        """Test that all events being ready is handled correctly."""
        self._ExpectSetup()
        self._ExpectEnumeration()
        self._ExpectHandle(self.nightly, 'events')
        self._ExpectHandle(self.weekly, 'events')
        self.mox.ReplayAll()

        self.driver.SetUpEventsAndTasks(self.config)
        self.driver.HandleEventsOnce()


    def testHandleNightlyEventOnce(self):
        """Test that one ready event is handled correctly."""
        self._ExpectSetup()
        self._ExpectEnumeration()
        self._ExpectHandle(self.nightly, 'events')
        self.weekly.ShouldHandle().InAnyOrder('events').AndReturn(False)
        self.mox.ReplayAll()

        self.driver.SetUpEventsAndTasks(self.config)
        self.driver.HandleEventsOnce()


if __name__ == '__main__':
    unittest.main()
