#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for site_utils/board_enumerator.py."""

import logging, mox, unittest

import base_event, board_enumerator, deduping_scheduler, driver
import forgiving_config_parser, manifest_versions, task, timed_event

from autotest_lib.server import frontend


class DriverTest(mox.MoxTestBase):
    """Unit tests for Driver."""


    def setUp(self):
        super(DriverTest, self).setUp()
        self.afe = self.mox.CreateMock(frontend.AFE)
        self.be = board_enumerator.BoardEnumerator(self.afe)
        self.ds = deduping_scheduler.DedupingScheduler(self.afe)
        self.mv = self.mox.CreateMock(manifest_versions.ManifestVersions)

        self.config = forgiving_config_parser.ForgivingConfigParser()
        self.nightly = self.mox.CreateMock(timed_event.Nightly)
        self.nightly.keyword = timed_event.Nightly.KEYWORD
        self.weekly = self.mox.CreateMock(timed_event.Weekly)
        self.weekly.keyword = timed_event.Weekly.KEYWORD

        self.driver = driver.Driver(self.ds, self.be)


    def _ExpectSetup(self):
        self.mox.StubOutWithMock(timed_event.Nightly, 'CreateFromConfig')
        self.mox.StubOutWithMock(timed_event.Weekly, 'CreateFromConfig')
        timed_event.Nightly.CreateFromConfig(
            mox.IgnoreArg(), self.mv).AndReturn(self.nightly)
        timed_event.Weekly.CreateFromConfig(
            mox.IgnoreArg(), self.mv).AndReturn(self.weekly)


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
        event.GetBranchBuildsForBoard(
            mox.IgnoreArg()).InAnyOrder(group).AndReturn(bbs)
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

        self.driver.SetUpEventsAndTasks(self.config, self.mv)
        self.driver.HandleEventsOnce(self.mv)


    def testHandleNightlyEventOnce(self):
        """Test that one ready event is handled correctly."""
        self._ExpectSetup()
        self._ExpectEnumeration()
        self._ExpectHandle(self.nightly, 'events')
        self.weekly.ShouldHandle().InAnyOrder('events').AndReturn(False)
        self.mox.ReplayAll()

        self.driver.SetUpEventsAndTasks(self.config, self.mv)
        self.driver.HandleEventsOnce(self.mv)


    def testForceOnceForBuild(self):
        """Test that one event being forced is handled correctly."""
        self._ExpectSetup()

        board = 'board'
        type = 'release'
        milestone = '00'
        manifest = '200.0.02'
        build = base_event.BuildName(board, type, milestone, manifest)

        self.nightly.Handle(mox.IgnoreArg(), {milestone: build}, board,
                            force=True)
        self.mox.ReplayAll()

        self.driver.SetUpEventsAndTasks(self.config, self.mv)
        self.driver.ForceEventsOnceForBuild([self.nightly.keyword], build)



if __name__ == '__main__':
    unittest.main()
