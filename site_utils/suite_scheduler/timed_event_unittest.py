#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for site_utils/timed_event.py."""

import datetime
import logging
import mox
import unittest

import forgiving_config_parser
import deduping_scheduler
import task
import timed_event


class TimedEventTestBase(mox.MoxTestBase):
    """Base class for TimedEvent unit test classes."""


    def setUp(self):
        super(TimedEventTestBase, self).setUp()
        self.mox.StubOutWithMock(timed_event.TimedEvent, '_now')


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
        timed_event.TimedEvent._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()

        t = self.CreateTrigger()  # Deadline gets set for a future time.
        self.assertFalse(t.ShouldHandle())
        self.mox.VerifyAll()

        self.mox.ResetAll()
        fake_now = self.TimeLaterThan(fake_now)  # Jump past that future time.
        timed_event.TimedEvent._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()
        self.assertTrue(t.ShouldHandle())


    def doTestDeadlineIsNow(self):
        """We happened to create the trigger at the exact right time."""
        timed_event.TimedEvent._now().MultipleTimes().AndReturn(self.BaseTime())
        self.mox.ReplayAll()
        to_test = self.CreateTrigger()
        self.assertTrue(to_test.ShouldHandle())


    def doTestTOCTOU(self):
        """Even if deadline passes during initialization, trigger must fire."""
        init_now = self.BaseTime() - datetime.timedelta(seconds=1)
        fire_now = self.BaseTime() + datetime.timedelta(seconds=1)
        timed_event.TimedEvent._now().AndReturn(init_now)
        timed_event.TimedEvent._now().AndReturn(fire_now)
        self.mox.ReplayAll()

        t = self.CreateTrigger()  # Deadline gets set for later tonight...
        # ...but has passed by the time we get around to firing.
        self.assertTrue(t.ShouldHandle())


class NightlyTest(TimedEventTestBase):
    """Unit tests for Weekly.

    @var _HOUR: The time of night to use in these unit tests.
    """

    _HOUR = 20


    def setUp(self):
        super(NightlyTest, self).setUp()


    def BaseTime(self):
        return datetime.datetime(2012, 1, 1, self._HOUR)


    def CreateTrigger(self):
        """Return an instance of timed_event.Nightly."""
        return timed_event.Nightly(self._HOUR, [])


    def testCreateFromConfig(self):
        """Test that creating from config is equivalent to using constructor."""
        config = forgiving_config_parser.ForgivingConfigParser()
        section = timed_event.TimedEvent.section_name(
            timed_event.Nightly.KEYWORD)
        config.add_section(section)
        config.set(section, 'hour', '%d' % self._HOUR)

        timed_event.TimedEvent._now().MultipleTimes().AndReturn(self.BaseTime())
        self.mox.ReplayAll()

        self.assertEquals(timed_event.Nightly(self._HOUR, []),
                          timed_event.Nightly.CreateFromConfig(config, []))


    def testCreateFromEmptyConfig(self):
        """Test that creating from empty config uses defaults."""
        config = forgiving_config_parser.ForgivingConfigParser()

        timed_event.TimedEvent._now().MultipleTimes().AndReturn(self.BaseTime())
        self.mox.ReplayAll()

        self.assertEquals(
            timed_event.Nightly(timed_event.Nightly._DEFAULT_HOUR, []),
            timed_event.Nightly.CreateFromConfig(config, []))


    def testDeadlineInPast(self):
        """Ensure we work if the deadline aready passed today."""
        fake_now = self.BaseTime() + datetime.timedelta(hours=1)
        timed_event.TimedEvent._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()

        nightly = self.CreateTrigger()  # Deadline gets set for tomorrow night.
        self.assertFalse(nightly.ShouldHandle())
        self.mox.VerifyAll()

        self.mox.ResetAll()
        fake_now += datetime.timedelta(days=1)  # Jump to tomorrow night.
        timed_event.TimedEvent._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()
        self.assertTrue(nightly.ShouldHandle())


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
    _HOUR = 22


    def setUp(self):
        super(WeeklyTest, self).setUp()


    def BaseTime(self):
        basetime = datetime.datetime(2012, 1, 1, self._HOUR)
        basetime += datetime.timedelta(self._DAY-basetime.weekday())
        return basetime


    def CreateTrigger(self):
        """Return an instance of timed_event.Weekly."""
        return timed_event.Weekly(self._DAY, self._HOUR, [])


    def testCreateFromConfig(self):
        """Test that creating from config is equivalent to using constructor."""
        config = forgiving_config_parser.ForgivingConfigParser()
        section = timed_event.TimedEvent.section_name(
            timed_event.Weekly.KEYWORD)
        config.add_section(section)
        config.set(section, 'day', '%d' % self._DAY)
        config.set(section, 'hour', '%d' % self._HOUR)

        timed_event.TimedEvent._now().MultipleTimes().AndReturn(self.BaseTime())
        self.mox.ReplayAll()

        self.assertEquals(timed_event.Weekly(self._DAY, self._HOUR, []),
                          timed_event.Weekly.CreateFromConfig(config, []))


    def testDeadlineInPast(self):
        """Ensure we work if the deadline already passed this week."""
        fake_now = self.BaseTime() + datetime.timedelta(days=1)
        timed_event.TimedEvent._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()

        weekly = self.CreateTrigger()  # Deadline gets set for next week.
        self.assertFalse(weekly.ShouldHandle())
        self.mox.VerifyAll()

        self.mox.ResetAll()
        fake_now += datetime.timedelta(days=1)  # Jump to tomorrow.
        timed_event.TimedEvent._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()
        self.assertFalse(weekly.ShouldHandle())
        self.mox.VerifyAll()

        self.mox.ResetAll()
        fake_now += datetime.timedelta(days=7)  # Jump to next week.
        timed_event.TimedEvent._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()
        self.assertTrue(weekly.ShouldHandle())


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
