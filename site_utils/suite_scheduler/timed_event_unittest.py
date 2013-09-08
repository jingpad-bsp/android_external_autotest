#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for site_utils/timed_event.py."""

import datetime, logging, mox, unittest

# driver must be imported first due to circular imports in base_event and task
import driver  # pylint: disable-msg=W0611
import base_event, deduping_scheduler, forgiving_config_parser
import manifest_versions, task, timed_event


class TimedEventTestBase(mox.MoxTestBase):
    """Base class for TimedEvent unit test classes."""


    def setUp(self):
        super(TimedEventTestBase, self).setUp()
        self.mox.StubOutWithMock(timed_event.TimedEvent, '_now')
        self.mv = self.mox.CreateMock(manifest_versions.ManifestVersions)


    def BaseTime(self):
        """Return the TimedEvent trigger-time as a datetime instance."""
        raise NotImplementedError()


    def CreateEvent(self):
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

        t = self.CreateEvent()  # Deadline gets set for a future time.
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
        to_test = self.CreateEvent()
        self.assertTrue(to_test.ShouldHandle())


    def doTestTOCTOU(self):
        """Even if deadline passes during initialization, trigger must fire."""
        init_now = self.BaseTime() - datetime.timedelta(seconds=1)
        fire_now = self.BaseTime() + datetime.timedelta(seconds=1)
        timed_event.TimedEvent._now().AndReturn(init_now)
        timed_event.TimedEvent._now().AndReturn(fire_now)
        self.mox.ReplayAll()

        t = self.CreateEvent()  # Deadline gets set for later tonight...
        # ...but has passed by the time we get around to firing.
        self.assertTrue(t.ShouldHandle())


    def doTestDeadlineUpdate(self, days_to_jump):
        fake_now = self.TimeBefore(self.BaseTime())
        timed_event.TimedEvent._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()

        nightly = self.CreateEvent()  # Deadline gets set for tonight.
        self.assertFalse(nightly.ShouldHandle())
        self.mox.VerifyAll()

        self.mox.ResetAll()
        fake_now = self.TimeLaterThan(self.BaseTime())  # Jump past deadline.
        timed_event.TimedEvent._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()

        self.assertTrue(nightly.ShouldHandle())
        nightly.UpdateCriteria()  # Deadline moves to tomorrow night
        self.assertFalse(nightly.ShouldHandle())
        self.mox.VerifyAll()

        self.mox.ResetAll()
        fake_now += datetime.timedelta(days=days_to_jump)  # Jump past deadline.
        timed_event.TimedEvent._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()
        self.assertTrue(nightly.ShouldHandle())


    def doTestGetBranchBuilds(self, days):
        board = 'faux_board'
        branch_manifests = {('factory','16'): ['last16'],
                            ('release','17'): ['first17', 'last17']}
        self.mv.ManifestsSinceDays(days, board).AndReturn(branch_manifests)
        timed_event.TimedEvent._now().MultipleTimes().AndReturn(self.BaseTime())
        self.mox.ReplayAll()

        branch_builds = self.CreateEvent().GetBranchBuildsForBoard(board)
        for (type, milestone), manifests in branch_manifests.iteritems():
            build = None
            if type in task.BARE_BRANCHES:
                self.assertEquals(len(branch_builds[type]), 1)
                build = branch_builds[type][0]
                self.assertTrue(build.startswith('%s-%s' % (board, type)))
            else:
                self.assertEquals(len(branch_builds[milestone]), 1)
                build = branch_builds[milestone][0]
                self.assertTrue(build.startswith('%s-release' % board))
            self.assertTrue('R%s-%s' % (milestone, manifests[-1]) in build)


class NightlyTest(TimedEventTestBase):
    """Unit tests for Weekly.

    @var _HOUR: The time of night to use in these unit tests.
    """

    _HOUR = 20


    def setUp(self):
        super(NightlyTest, self).setUp()


    def BaseTime(self):
        return datetime.datetime(2012, 1, 1, self._HOUR)


    def CreateEvent(self):
        """Return an instance of timed_event.Nightly."""
        return timed_event.Nightly(self.mv, False, self._HOUR)


    def testCreateFromConfig(self):
        """Test that creating from config is equivalent to using constructor."""
        config = forgiving_config_parser.ForgivingConfigParser()
        section = base_event.SectionName(timed_event.Nightly.KEYWORD)
        config.add_section(section)
        config.set(section, 'hour', '%d' % self._HOUR)

        timed_event.TimedEvent._now().MultipleTimes().AndReturn(self.BaseTime())
        self.mox.ReplayAll()

        self.assertEquals(self.CreateEvent(),
                          timed_event.Nightly.CreateFromConfig(config, self.mv))


    def testCreateFromEmptyConfig(self):
        """Test that creating from empty config uses defaults."""
        config = forgiving_config_parser.ForgivingConfigParser()

        timed_event.TimedEvent._now().MultipleTimes().AndReturn(self.BaseTime())
        self.mox.ReplayAll()

        self.assertEquals(
            timed_event.Nightly(self.mv, False,
                                timed_event.Nightly._DEFAULT_HOUR),
            timed_event.Nightly.CreateFromConfig(config, self.mv))


    def testCreateFromAlwaysHandleConfig(self):
        """Test that creating with always_handle works as intended."""
        config = forgiving_config_parser.ForgivingConfigParser()
        section = base_event.SectionName(timed_event.Nightly.KEYWORD)
        config.add_section(section)
        config.set(section, 'hour', '%d' % (self._HOUR + 1))
        config.set(section, 'always_handle', 'True')

        timed_event.TimedEvent._now().MultipleTimes().AndReturn(self.BaseTime())
        self.mox.ReplayAll()

        event = timed_event.Nightly.CreateFromConfig(config, self.mv)
        self.assertTrue(event.ShouldHandle())


    def testMerge(self):
        """Test that Merge() works when the deadline time of day changes."""
        timed_event.TimedEvent._now().MultipleTimes().AndReturn(self.BaseTime())
        self.mox.ReplayAll()

        old = timed_event.Nightly(self.mv, False, self._HOUR)
        new = timed_event.Nightly(self.mv, False, (self._HOUR + 23) % 24)
        self.assertNotEquals(old._deadline, new._deadline)
        old.Merge(new)
        self.assertEquals(old._deadline, new._deadline)


    def testSkipMerge(self):
        """Test that deadline is unchanged when time of day is unchanged."""
        timed_event.TimedEvent._now().MultipleTimes().AndReturn(self.BaseTime())
        self.mox.ReplayAll()

        old = timed_event.Nightly(self.mv, False, self._HOUR)
        new = timed_event.Nightly(self.mv, False, self._HOUR)
        new._deadline += datetime.timedelta(days=1)
        self.assertNotEquals(old._deadline, new._deadline)
        saved_deadline = old._deadline
        old.Merge(new)
        self.assertEquals(saved_deadline, old._deadline)


    def testDeadlineInPast(self):
        """Ensure we work if the deadline aready passed today."""
        fake_now = self.BaseTime() + datetime.timedelta(hours=1)
        timed_event.TimedEvent._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()

        nightly = self.CreateEvent()  # Deadline gets set for tomorrow night.
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


    def testDeadlineUpdate(self):
        """Ensure we update the deadline correctly."""
        self.doTestDeadlineUpdate(days_to_jump=1)


    def testGetBranchBuilds(self):
        """Ensure Nightly gets most recent builds in last day."""
        self.doTestGetBranchBuilds(days=1)


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


    def CreateEvent(self):
        """Return an instance of timed_event.Weekly."""
        return timed_event.Weekly(self.mv, False, self._DAY, self._HOUR)


    def testCreateFromConfig(self):
        """Test that creating from config is equivalent to using constructor."""
        config = forgiving_config_parser.ForgivingConfigParser()
        section = base_event.SectionName(timed_event.Weekly.KEYWORD)
        config.add_section(section)
        config.set(section, 'day', '%d' % self._DAY)
        config.set(section, 'hour', '%d' % self._HOUR)

        timed_event.TimedEvent._now().MultipleTimes().AndReturn(self.BaseTime())
        self.mox.ReplayAll()

        self.assertEquals(self.CreateEvent(),
                          timed_event.Weekly.CreateFromConfig(config, self.mv))


    def testMergeDueToTimeChange(self):
        """Test that Merge() works when the deadline time of day changes."""
        timed_event.TimedEvent._now().MultipleTimes().AndReturn(self.BaseTime())
        self.mox.ReplayAll()

        old = timed_event.Weekly(self.mv, False, self._DAY, self._HOUR)
        new = timed_event.Weekly(self.mv, False, self._DAY, self._HOUR + 1)
        self.assertNotEquals(old._deadline, new._deadline)
        old.Merge(new)
        self.assertEquals(old._deadline, new._deadline)


    def testMergeDueToDayChange(self):
        """Test that Merge() works when the deadline day of week changes."""
        timed_event.TimedEvent._now().MultipleTimes().AndReturn(self.BaseTime())
        self.mox.ReplayAll()

        old = timed_event.Weekly(self.mv, False, self._DAY, self._HOUR)
        new = timed_event.Weekly(self.mv, False, self._DAY, self._HOUR)
        new._deadline += datetime.timedelta(days=1)
        self.assertNotEquals(old._deadline, new._deadline)
        old.Merge(new)
        self.assertEquals(old._deadline, new._deadline)


    def testSkipMerge(self):
        """Test that deadline is unchanged when only the week is changed."""
        timed_event.TimedEvent._now().MultipleTimes().AndReturn(self.BaseTime())
        self.mox.ReplayAll()

        old = timed_event.Weekly(self.mv, False, self._DAY, self._HOUR)
        new = timed_event.Weekly(self.mv, False, self._DAY, self._HOUR)
        new._deadline += datetime.timedelta(days=7)
        self.assertNotEquals(old._deadline, new._deadline)
        saved_deadline = old._deadline
        old.Merge(new)
        self.assertEquals(saved_deadline, old._deadline)


    def testDeadlineInPast(self):
        """Ensure we work if the deadline already passed this week."""
        fake_now = self.BaseTime() + datetime.timedelta(days=1)
        timed_event.TimedEvent._now().MultipleTimes().AndReturn(fake_now)
        self.mox.ReplayAll()

        weekly = self.CreateEvent()  # Deadline gets set for next week.
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


    def testDeadlineUpdate(self):
        """Ensure we update the deadline correctly."""
        self.doTestDeadlineUpdate(days_to_jump=7)


    def testGetBranchBuilds(self):
        """Ensure Weekly gets most recent builds in last 7 days."""
        self.doTestGetBranchBuilds(days=7)


if __name__ == '__main__':
  unittest.main()
