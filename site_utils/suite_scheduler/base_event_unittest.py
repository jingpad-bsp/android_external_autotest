#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for site_utils/base_event.py."""

import logging
import mox
import unittest

import base_event
import deduping_scheduler
import task


class FakeTask(task.Task):
    """A mock Task that can optionally expect triggering."""
    def __init__(self, suite, build, pool, pymox):
        super(FakeTask, self).__init__(suite, build, pool)
        pymox.StubOutWithMock(self, 'Run')


    def Arm(self):
        """Expect to be triggered along with any other FakeTasks."""
        self.Run(mox.IgnoreArg(),
                 mox.IgnoreArg(),
                 mox.IgnoreArg(),
                 mox.IgnoreArg()).InAnyOrder('tasks').AndReturn(True)


class FakeOneShot(FakeTask):
    """A mock OneShotEvent that can be optionally set to expect triggering."""
    def __init__(self, suite, build, pool, pymox):
        super(FakeOneShot, self).__init__(suite, build, pool, pymox)


    def Arm(self):
        """Expect to be triggered once, and to ask for self-destruction."""
        self.Run(mox.IgnoreArg(),
                 mox.IgnoreArg(),
                 mox.IgnoreArg(),
                 mox.IgnoreArg()).AndReturn(False)


class BaseEventTest(mox.MoxTestBase):
    """Unit tests for BaseEvent.

    @var _TASKS: Specs for several tasks to run.
    """


    _TASKS = [('suite1', 'build1', 'pool'),
              ('suite2', 'build2', None),
              ('suite2', 'build3', None),
              ('suite3', 'build2', None)]


    def setUp(self):
        super(BaseEventTest, self).setUp()
        self.sched = self.mox.CreateMock(deduping_scheduler.DedupingScheduler)


    def testEventDeduping(self):
        """Tests that tasks are de-duped at BaseEvent creation."""
        tasks = [FakeTask(*task, pymox=self.mox) for task in self._TASKS]
        tasks.append(FakeTask(*self._TASKS[0], pymox=self.mox))
        self.mox.ReplayAll()

        event = base_event.BaseEvent('new_build')
        event.tasks = tasks
        self.assertEquals(len(event.tasks), len(self._TASKS))


    def testRecurringTasks(self):
        """Tests that tasks are all run on Handle()."""
        tasks = [FakeTask(*task, pymox=self.mox) for task in self._TASKS]
        for task in tasks: task.Arm()
        self.mox.ReplayAll()

        new_build = base_event.BaseEvent('new_build')
        new_build.tasks = tasks
        new_build.Handle(self.sched, {}, [])
        self.mox.VerifyAll()

        # Ensure that all tasks are still around and can be Handle()'d again.
        self.mox.ResetAll()
        for task in tasks: task.Arm()
        self.mox.ReplayAll()
        new_build.Handle(self.sched, {}, [])


    def testOneShotWithRecurringTasks(self):
        """Tests that one-shot tasks are destroyed correctly."""
        tasks = [FakeTask(*task, pymox=self.mox) for task in self._TASKS]
        all_tasks = tasks + [FakeOneShot(*self._TASKS[0], pymox=self.mox)]
        for task in all_tasks: task.Arm()
        self.mox.ReplayAll()

        new_build = base_event.BaseEvent('new_build')
        new_build.tasks = all_tasks
        new_build.Handle(self.sched, {}, [])
        self.mox.VerifyAll()

        # Ensure that only recurring tasks can get Handle()'d again.
        self.mox.ResetAll()
        for task in tasks: task.Arm()
        self.mox.ReplayAll()
        new_build.Handle(self.sched, {}, [])
