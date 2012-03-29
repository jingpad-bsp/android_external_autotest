#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for site_utils/triggerable_job.py."""

import logging
import mox
import unittest

import deduping_scheduler
import triggerable_event


class TriggerableEventTestBase(mox.MoxTestBase):
    """Common code for TriggerableEvent test classes

    @var _BUILD: fake build
    @var _BOARD: fake board to reimage
    @var _SUITE: fake suite name
    """

    _BUILD = 'build'
    _BOARD = 'board'
    _SUITE = 'suite'


    def setUp(self):
        super(TriggerableEventTestBase, self).setUp()
        self.sched = self.mox.CreateMock(deduping_scheduler.DedupingScheduler)


class TriggerableEventTest(TriggerableEventTestBase):
    """Unit tests for TriggerableEvent."""


    def setUp(self):
        super(TriggerableEventTest, self).setUp()
        self.job = triggerable_event.TriggerableEvent(self._SUITE, self._BOARD,
                                                      self._BUILD)


    def testTrigger(self):
        """Test triggering a recurring triggerable job."""
        self.sched.ScheduleSuite(self._SUITE, self._BOARD, self._BUILD,
                                 None, False).AndReturn(True)
        self.mox.ReplayAll()
        self.assertTrue(self.job.Trigger(self.sched))


    def testTriggerDuplicate(self):
        """Test triggering a duplicate suite job."""
        self.sched.ScheduleSuite(self._SUITE, self._BOARD, self._BUILD,
                                 None, False).AndReturn(False)
        self.mox.ReplayAll()
        self.assertTrue(self.job.Trigger(self.sched))


    def testTriggerExplodes(self):
        """Test a failure to schedule while triggering job."""
        # Barf while scheduling.
        self.sched.ScheduleSuite(
            self._SUITE, self._BOARD, self._BUILD, None, False).AndRaise(
                deduping_scheduler.ScheduleException('Simulated Failure'))
        self.mox.ReplayAll()
        self.assertTrue(self.job.Trigger(self.sched))


    def testForceTrigger(self):
        """Test force triggering a recurring triggerable job."""
        self.sched.ScheduleSuite(self._SUITE, self._BOARD, self._BUILD,
                                 None, True).AndReturn(True)
        self.mox.ReplayAll()
        self.assertTrue(self.job.Trigger(self.sched, force=True))


    def testHash(self):
        """Test hash function for TriggerableEvent classes."""
        same_job = triggerable_event.TriggerableEvent(self._SUITE, self._BOARD,
                                                      self._BUILD)
        other_job = triggerable_event.TriggerableEvent(self._SUITE, self._BOARD,
                                                       self._BUILD+'2')
        self.assertEquals(hash(self.job), hash(same_job))
        self.assertNotEquals(hash(self.job), hash(other_job))


class OneShotEventTest(TriggerableEventTestBase):
    """Unit tests for OneShotEvent."""


    def setUp(self):
        super(OneShotEventTest, self).setUp()
        self.job = triggerable_event.OneShotEvent(self._SUITE, self._BOARD,
                                                  self._BUILD)


    def testTrigger(self):
        """Test triggering a one-shot triggerable job."""
        self.sched.ScheduleSuite(self._SUITE, self._BOARD, self._BUILD,
                                 None, False).AndReturn(True)
        self.mox.ReplayAll()
        self.assertFalse(self.job.Trigger(self.sched))


    def testTriggerDuplicate(self):
        """Test triggering a duplicate suite job."""
        self.sched.ScheduleSuite(self._SUITE, self._BOARD, self._BUILD,
                                 None, False).AndReturn(False)
        self.mox.ReplayAll()
        self.assertFalse(self.job.Trigger(self.sched))


    def testTriggerExplodes(self):
        """Test a failure to schedule while triggering job."""
        # Barf while scheduling.
        self.sched.ScheduleSuite(
            self._SUITE, self._BOARD, self._BUILD, None, False).AndRaise(
                deduping_scheduler.ScheduleException('Simulated Failure'))
        self.mox.ReplayAll()
        self.assertFalse(self.job.Trigger(self.sched))


    def testForceTrigger(self):
        """Test force triggering a one-shot triggerable job."""
        self.sched.ScheduleSuite(self._SUITE, self._BOARD, self._BUILD,
                                 None, True).AndReturn(True)
        self.mox.ReplayAll()
        self.assertFalse(self.job.Trigger(self.sched, force=True))


if __name__ == '__main__':
    unittest.main()
