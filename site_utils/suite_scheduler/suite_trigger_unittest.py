#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for site_utils/trigger.py.

See http://crosbug.com/28739 for why this file isn't trigger_unittest.py
"""

import datetime
import logging
import mox
import unittest

import deduping_scheduler
import trigger
import triggerable_event


class FakeTriggerable(triggerable_event.TriggerableEvent):
    """A mock TriggerableEvent that can optionally expect triggering."""
    def __init__(self, suite, board, build, pool, pymox):
        super(FakeTriggerable, self).__init__(suite, board, build, pool)
        pymox.StubOutWithMock(self, 'Trigger')


    def Arm(self):
        """Expect to be triggered along with any other FakeTriggerables."""
        self.Trigger(mox.IgnoreArg(),
                     mox.IgnoreArg()).InAnyOrder('events').AndReturn(True)


class FakeOneShot(FakeTriggerable):
    """A mock OneShotEvent that can be optionally set to expect triggering."""
    def __init__(self, suite, board, build, pool, pymox):
        super(FakeOneShot, self).__init__(suite, board, build, pool, pymox)


    def Arm(self):
        """Expect to be triggered once, and to ask for self-destruction."""
        self.Trigger(mox.IgnoreArg(), mox.IgnoreArg()).AndReturn(False)


class BaseTriggerTest(mox.MoxTestBase):
    """Unit tests for BaseTrigger.

    @var _EVENTS: Specs for several events to trigger.
    """


    _EVENTS = [('suite1', 'board1', 'build1', 'pool'),
               ('suite2', 'board2', 'build2', None),
               ('suite2', 'board2', 'build3', None),
               ('suite3', 'board2', 'build2', None)]


    def setUp(self):
        super(BaseTriggerTest, self).setUp()
        self.sched = self.mox.CreateMock(deduping_scheduler.DedupingScheduler)


    def testEventDeduping(self):
        """Tests that events are de-duped at BaseTrigger creation."""
        events = [FakeTriggerable(*e, pymox=self.mox) for e in self._EVENTS]
        events.append(FakeTriggerable(*self._EVENTS[0], pymox=self.mox))
        self.mox.ReplayAll()

        self.assertEquals(len(trigger.BaseTrigger('new_build', events)._events),
                          len(self._EVENTS))


    def testRecurringEvents(self):
        """Tests that events are all run on Fire()."""
        events = [FakeTriggerable(*e, pymox=self.mox) for e in self._EVENTS]
        for event in events: event.Arm()
        self.mox.ReplayAll()

        new_build = trigger.BaseTrigger('new_build', events)
        new_build.Fire(self.sched)
        self.mox.VerifyAll()

        # Ensure that all the events are still around and can Fire again.
        self.mox.ResetAll()
        for event in events: event.Arm()
        self.mox.ReplayAll()
        new_build.Fire(self.sched)


    def testOneShotWithRecurringEvents(self):
        """Tests that one-shot events are destroyed correctly."""
        events = [FakeTriggerable(*e, pymox=self.mox) for e in self._EVENTS]
        all_events = events + [FakeOneShot(*self._EVENTS[0], pymox=self.mox)]
        for event in all_events: event.Arm()
        self.mox.ReplayAll()

        new_build = trigger.BaseTrigger('new_build', all_events)
        new_build.Fire(self.sched)
        self.mox.VerifyAll()

        # Ensure that only recurring events are still around and can Fire again.
        self.mox.ResetAll()
        for event in events: event.Arm()
        self.mox.ReplayAll()
        new_build.Fire(self.sched)


class TimedTriggerTestBase(mox.MoxTestBase):
    """Base class for TimedTrigger unit test classes."""


    def setUp(self):
        super(TimedTriggerTestBase, self).setUp()
        self.mox.StubOutWithMock(trigger.TimedTrigger, '_now')


    def BaseTime(self):
        """Return the TimedTrigger trigger-time as a datetime instance."""
        raise NotImplementedError()


    def CreateTrigger(self):
        """Return an instance of the TimedTrigger subclass being tested."""
        raise NotImplementedError()


    def TimeBefore(self, now):
        """Return a datetime that's before |now|."""
        raise NotImplementedError()


    def TimeLaterThan(self, now):
        """Return a datetime that's later than |now|."""
        raise NotImplementedError()


    def doTestDeadlineInFuture(self):
        fake_now = self.TimeBefore(self.BaseTime())
        trigger.TimedTrigger._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()

        t = self.CreateTrigger()  # Deadline gets set for a future time.
        self.assertFalse(t.ShouldFire())
        self.mox.VerifyAll()

        self.mox.ResetAll()
        fake_now = self.TimeLaterThan(fake_now)  # Jump past that future time.
        trigger.TimedTrigger._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()
        self.assertTrue(t.ShouldFire())


    def doTestDeadlineIsNow(self):
        """We happened to create the trigger at the exact right time."""
        trigger.TimedTrigger._now().MultipleTimes().AndReturn(self.BaseTime())
        self.mox.ReplayAll()
        to_test = self.CreateTrigger()
        self.assertTrue(to_test.ShouldFire())


    def doTestTOCTOU(self):
        """Even if deadline passes during initialization, trigger must fire."""
        init_now = self.BaseTime() - datetime.timedelta(seconds=1)
        fire_now = self.BaseTime() + datetime.timedelta(seconds=1)
        trigger.TimedTrigger._now().AndReturn(init_now)
        trigger.TimedTrigger._now().AndReturn(fire_now)
        self.mox.ReplayAll()

        t = self.CreateTrigger()  # Deadline gets set for later tonight...
        # ...but has passed by the time we get around to firing.
        self.assertTrue(t.ShouldFire())


class NightlyTest(TimedTriggerTestBase):
    """Unit tests for Weekly.

    @var _HOUR: The time of night to use in these unit tests.
    """


    _HOUR = 21


    def setUp(self):
        super(NightlyTest, self).setUp()


    def BaseTime(self):
        return datetime.datetime(2012, 1, 1, self._HOUR)


    def CreateTrigger(self):
        """Return an instance of trigger.Nightly."""
        return trigger.Nightly(self._HOUR, [])


    def testDeadlineInPast(self):
        """Ensure we work if the deadline aready passed today."""
        fake_now = self.BaseTime() + datetime.timedelta(hours=1)
        trigger.TimedTrigger._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()

        nightly = self.CreateTrigger()  # Deadline gets set for tomorrow night.
        self.assertFalse(nightly.ShouldFire())
        self.mox.VerifyAll()

        self.mox.ResetAll()
        fake_now += datetime.timedelta(days=1)  # Jump to tomorrow night.
        trigger.TimedTrigger._now().MultipleTimes().AndReturn(fake_now)
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


class WeeklyTest(TimedTriggerTestBase):
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
        """Return an instance of trigger.Weekly."""
        return trigger.Weekly(self._DAY, self._HOUR, [])


    def testDeadlineInPast(self):
        """Ensure we work if the deadline already passed this week."""
        fake_now = self.BaseTime() + datetime.timedelta(days=1)
        trigger.TimedTrigger._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()

        weekly = self.CreateTrigger()  # Deadline gets set for next week.
        self.assertFalse(weekly.ShouldFire())
        self.mox.VerifyAll()

        self.mox.ResetAll()
        fake_now += datetime.timedelta(days=1)  # Jump to tomorrow.
        trigger.TimedTrigger._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()
        self.assertFalse(weekly.ShouldFire())
        self.mox.VerifyAll()

        self.mox.ResetAll()
        fake_now += datetime.timedelta(days=7)  # Jump to next week.
        trigger.TimedTrigger._now().MultipleTimes().AndReturn(fake_now)
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
