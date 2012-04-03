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
import task


class TaskTestBase(mox.MoxTestBase):
    """Common code for Task test classes

    @var _BUILD: fake build
    @var _BOARDS: fake boards to reimage
    @var _SUITE: fake suite name
    """

    _BUILD = 'build'
    _BOARDS = ['board1']
    _SUITE = 'suite'


    def setUp(self):
        super(TaskTestBase, self).setUp()
        self.sched = self.mox.CreateMock(deduping_scheduler.DedupingScheduler)


class TaskTest(TaskTestBase):
    """Unit tests for Task."""


    def setUp(self):
        super(TaskTest, self).setUp()
        self.job = task.Task(self._SUITE, self._BUILD)


    def testRun(self):
        """Test triggering a recurring triggerable job."""
        self.sched.ScheduleSuite(self._SUITE, self._BOARDS[0], self._BUILD,
                                 None, False).AndReturn(True)
        self.mox.ReplayAll()
        self.assertTrue(self.job.Run(self.sched, self._BOARDS))


    def testRunMultipleBoards(self):
        """Test triggering a recurring triggerable job for >1 board."""
        boards = ['mboard1', 'mboard2']
        for board in boards:
            self.sched.ScheduleSuite(self._SUITE, board, self._BUILD,
                                     None, False).AndReturn(True)
        self.mox.ReplayAll()
        self.assertTrue(self.job.Run(self.sched, boards))


    def testRunDuplicate(self):
        """Test triggering a duplicate suite job."""
        self.sched.ScheduleSuite(self._SUITE, self._BOARDS[0], self._BUILD,
                                 None, False).AndReturn(False)
        self.mox.ReplayAll()
        self.assertTrue(self.job.Run(self.sched, self._BOARDS))


    def testRunExplodes(self):
        """Test a failure to schedule while triggering job."""
        # Barf while scheduling.
        self.sched.ScheduleSuite(
            self._SUITE, self._BOARDS[0], self._BUILD, None, False).AndRaise(
                deduping_scheduler.ScheduleException('Simulated Failure'))
        self.mox.ReplayAll()
        self.assertTrue(self.job.Run(self.sched, self._BOARDS))


    def testForceRun(self):
        """Test force triggering a recurring triggerable job."""
        self.sched.ScheduleSuite(self._SUITE, self._BOARDS[0], self._BUILD,
                                 None, True).AndReturn(True)
        self.mox.ReplayAll()
        self.assertTrue(self.job.Run(self.sched, self._BOARDS, force=True))


    def testHash(self):
        """Test hash function for Task classes."""
        same_job = task.Task(self._SUITE, self._BUILD)
        other_job = task.Task(self._SUITE, self._BUILD+'2', 'pool')
        self.assertEquals(hash(self.job), hash(same_job))
        self.assertNotEquals(hash(self.job), hash(other_job))


class OneShotTaskTest(TaskTestBase):
    """Unit tests for OneShotTask."""


    def setUp(self):
        super(OneShotTaskTest, self).setUp()
        self.job = task.OneShotTask(self._SUITE, self._BUILD)


    def testRun(self):
        """Test triggering a one-shot triggerable job."""
        self.sched.ScheduleSuite(self._SUITE, self._BOARDS[0], self._BUILD,
                                 None, False).AndReturn(True)
        self.mox.ReplayAll()
        self.assertFalse(self.job.Run(self.sched, self._BOARDS))


    def testRunDuplicate(self):
        """Test triggering a duplicate suite job."""
        self.sched.ScheduleSuite(self._SUITE, self._BOARDS[0], self._BUILD,
                                 None, False).AndReturn(False)
        self.mox.ReplayAll()
        self.assertFalse(self.job.Run(self.sched, self._BOARDS))


    def testRunExplodes(self):
        """Test a failure to schedule while triggering job."""
        # Barf while scheduling.
        self.sched.ScheduleSuite(
            self._SUITE, self._BOARDS[0], self._BUILD, None, False).AndRaise(
                deduping_scheduler.ScheduleException('Simulated Failure'))
        self.mox.ReplayAll()
        self.assertFalse(self.job.Run(self.sched, self._BOARDS))


    def testForceRun(self):
        """Test force triggering a one-shot triggerable job."""
        self.sched.ScheduleSuite(self._SUITE, self._BOARDS[0], self._BUILD,
                                 None, True).AndReturn(True)
        self.mox.ReplayAll()
        self.assertFalse(self.job.Run(self.sched, self._BOARDS, force=True))


if __name__ == '__main__':
    unittest.main()
