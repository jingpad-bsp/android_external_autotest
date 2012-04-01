#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for site_utils/event.py.

See http://crosbug.com/28739 for why this file isn't trigger_unittest.py
"""

import datetime
import logging
import mox
import unittest

import deduping_scheduler
import event
import task


class FakeTask(task.Task):
    """A mock Task that can optionally expect triggering."""
    def __init__(self, suite, board, build, pool, pymox):
        super(FakeTask, self).__init__(suite, board, build, pool)
        pymox.StubOutWithMock(self, 'Run')


    def Arm(self):
        """Expect to be triggered along with any other FakeTasks."""
        self.Run(mox.IgnoreArg(),
                 mox.IgnoreArg()).InAnyOrder('tasks').AndReturn(True)


class FakeOneShot(FakeTask):
    """A mock OneShotEvent that can be optionally set to expect triggering."""
    def __init__(self, suite, board, build, pool, pymox):
        super(FakeOneShot, self).__init__(suite, board, build, pool, pymox)


    def Arm(self):
        """Expect to be triggered once, and to ask for self-destruction."""
        self.Run(mox.IgnoreArg(), mox.IgnoreArg()).AndReturn(False)


class BaseEventTest(mox.MoxTestBase):
    """Unit tests for BaseEvent.

    @var _TASKS: Specs for several tasks to run.
    """


    _TASKS = [('suite1', 'board1', 'build1', 'pool'),
              ('suite2', 'board2', 'build2', None),
              ('suite2', 'board2', 'build3', None),
              ('suite3', 'board2', 'build2', None)]


    def setUp(self):
        super(BaseEventTest, self).setUp()
        self.sched = self.mox.CreateMock(deduping_scheduler.DedupingScheduler)


    def testEventDeduping(self):
        """Tests that tasks are de-duped at BaseEvent creation."""
        tasks = [FakeTask(*task, pymox=self.mox) for task in self._TASKS]
        tasks.append(FakeTask(*self._TASKS[0], pymox=self.mox))
        self.mox.ReplayAll()

        self.assertEquals(len(event.BaseEvent('new_build', tasks)._tasks),
                          len(self._TASKS))


    def testRecurringTasks(self):
        """Tests that tasks are all run on Fire()."""
        tasks = [FakeTask(*task, pymox=self.mox) for task in self._TASKS]
        for task in tasks: task.Arm()
        self.mox.ReplayAll()

        new_build = event.BaseEvent('new_build', tasks)
        new_build.Fire(self.sched)
        self.mox.VerifyAll()

        # Ensure that all the tasks are still around and can Fire again.
        self.mox.ResetAll()
        for task in tasks: task.Arm()
        self.mox.ReplayAll()
        new_build.Fire(self.sched)


    def testOneShotWithRecurringTasks(self):
        """Tests that one-shot tasks are destroyed correctly."""
        tasks = [FakeTask(*task, pymox=self.mox) for task in self._TASKS]
        all_tasks = tasks + [FakeOneShot(*self._TASKS[0], pymox=self.mox)]
        for task in all_tasks: task.Arm()
        self.mox.ReplayAll()

        new_build = event.BaseEvent('new_build', all_tasks)
        new_build.Fire(self.sched)
        self.mox.VerifyAll()

        # Ensure that only recurring tasks are still around and can Fire again.
        self.mox.ResetAll()
        for task in tasks: task.Arm()
        self.mox.ReplayAll()
        new_build.Fire(self.sched)


class TimedEventTestBase(mox.MoxTestBase):
    """Base class for TimedEvent unit test classes."""


    def setUp(self):
        super(TimedEventTestBase, self).setUp()
        self.mox.StubOutWithMock(event.TimedEvent, '_now')


    def BaseTime(self):
        """Return the TimedEvent trigger-time as a datetime instance."""
        raise NotImplementedError()


    def CreateTrigger(self):
        """Return an instance of the TimedEvent subclass being tested."""
        raise NotImplementedError()


    def TimeBefore(self, now):
        """Return a datetime that's before |now|."""
        raise NotImplementedError()


    def TimeLaterThan(self, now):
        """Return a datetime that's later than |now|."""
        raise NotImplementedError()


    def doTestDeadlineInFuture(self):
        fake_now = self.TimeBefore(self.BaseTime())
        event.TimedEvent._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()

        t = self.CreateTrigger()  # Deadline gets set for a future time.
        self.assertFalse(t.ShouldFire())
        self.mox.VerifyAll()

        self.mox.ResetAll()
        fake_now = self.TimeLaterThan(fake_now)  # Jump past that future time.
        event.TimedEvent._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()
        self.assertTrue(t.ShouldFire())


    def doTestDeadlineIsNow(self):
        """We happened to create the trigger at the exact right time."""
        event.TimedEvent._now().MultipleTimes().AndReturn(self.BaseTime())
        self.mox.ReplayAll()
        to_test = self.CreateTrigger()
        self.assertTrue(to_test.ShouldFire())


    def doTestTOCTOU(self):
        """Even if deadline passes during initialization, trigger must fire."""
        init_now = self.BaseTime() - datetime.timedelta(seconds=1)
        fire_now = self.BaseTime() + datetime.timedelta(seconds=1)
        event.TimedEvent._now().AndReturn(init_now)
        event.TimedEvent._now().AndReturn(fire_now)
        self.mox.ReplayAll()

        t = self.CreateTrigger()  # Deadline gets set for later tonight...
        # ...but has passed by the time we get around to firing.
        self.assertTrue(t.ShouldFire())


class NightlyTest(TimedEventTestBase):
    """Unit tests for Weekly.

    @var _HOUR: The time of night to use in these unit tests.
    """


    _HOUR = 21


    def setUp(self):
        super(NightlyTest, self).setUp()


    def BaseTime(self):
        return datetime.datetime(2012, 1, 1, self._HOUR)


    def CreateTrigger(self):
        """Return an instance of event.Nightly."""
        return event.Nightly(self._HOUR, [])


    def testDeadlineInPast(self):
        """Ensure we work if the deadline aready passed today."""
        fake_now = self.BaseTime() + datetime.timedelta(hours=1)
        event.TimedEvent._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()

        nightly = self.CreateTrigger()  # Deadline gets set for tomorrow night.
        self.assertFalse(nightly.ShouldFire())
        self.mox.VerifyAll()

        self.mox.ResetAll()
        fake_now += datetime.timedelta(days=1)  # Jump to tomorrow night.
        event.TimedEvent._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()
        self.assertTrue(nightly.ShouldFire())


    def TimeBefore(self, now):
        return now - datetime.timedelta(hours=1)


    def TimeLaterThan(self, now):
        return now + datetime.timedelta(hours=2)


    def testDeadlineInFuture(self):
        """Ensure we work if the deadline is later today."""
        self.doTestDeadlineInFuture()


    def testDeadlineIsNow(self):
        """We happened to create the trigger at the exact right time."""
        self.doTestDeadlineIsNow()


    def testTOCTOU(self):
        """Even if deadline passes during initialization, trigger must fire."""
        self.doTestTOCTOU()


class WeeklyTest(TimedEventTestBase):
    """Unit tests for Weekly.

    @var _DAY: The day of the week to use in these unit tests.
    @var _HOUR: The time of night to use in these unit tests.
    """


    _DAY = 5
    _HOUR = 23


    def setUp(self):
        super(WeeklyTest, self).setUp()


    def BaseTime(self):
        basetime = datetime.datetime(2012, 1, 1, self._HOUR)
        basetime += datetime.timedelta(self._DAY-basetime.weekday())
        return basetime


    def CreateTrigger(self):
        """Return an instance of event.Weekly."""
        return event.Weekly(self._DAY, self._HOUR, [])


    def testDeadlineInPast(self):
        """Ensure we work if the deadline already passed this week."""
        fake_now = self.BaseTime() + datetime.timedelta(days=1)
        event.TimedEvent._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()

        weekly = self.CreateTrigger()  # Deadline gets set for next week.
        self.assertFalse(weekly.ShouldFire())
        self.mox.VerifyAll()

        self.mox.ResetAll()
        fake_now += datetime.timedelta(days=1)  # Jump to tomorrow.
        event.TimedEvent._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()
        self.assertFalse(weekly.ShouldFire())
        self.mox.VerifyAll()

        self.mox.ResetAll()
        fake_now += datetime.timedelta(days=7)  # Jump to next week.
        event.TimedEvent._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()
        self.assertTrue(weekly.ShouldFire())


    def TimeBefore(self, now):
        return now - datetime.timedelta(days=1)


    def TimeLaterThan(self, now):
        return now + datetime.timedelta(days=2)


    def testDeadlineInFuture(self):
        """Ensure we work if the deadline is later this week."""
        self.doTestDeadlineInFuture()


    def testDeadlineIsNow(self):
        """We happened to create the trigger at the exact right time."""
        self.doTestDeadlineIsNow()


    def testTOCTOU(self):
        """Even if deadline passes during initialization, trigger must fire."""
        self.doTestTOCTOU()


if __name__ == '__main__':
  unittest.main()
