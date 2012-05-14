#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for site_utils/deduping_scheduler.py."""

import logging
import mox
import unittest

import deduping_scheduler

from autotest_lib.server import frontend


class DedupingSchedulerTest(mox.MoxTestBase):
    """Unit tests for DedupingScheduler

    @var _BUILD: fake build
    @var _BOARD: fake board to reimage
    @var _SUITE: fake suite name
    @var _POOL: fake machine pool name
    """

    _BUILD = 'build'
    _BOARD = 'board'
    _SUITE = 'suite'
    _POOL = 'pool'


    def setUp(self):
        super(DedupingSchedulerTest, self).setUp()
        self.afe = self.mox.CreateMock(frontend.AFE)
        self.scheduler = deduping_scheduler.DedupingScheduler(afe=self.afe)


    def testScheduleSuite(self):
        """Test a successful de-dup and suite schedule."""
        # A similar suite has not already been scheduled.
        self.afe.get_jobs(name__startswith=self._BUILD,
                          name__endswith='control.'+self._SUITE).AndReturn([])
        # Expect an attempt to schedule; allow it to succeed.
        self.afe.run('create_suite_job',
                     suite_name=self._SUITE,
                     board=self._BOARD,
                     build=self._BUILD,
                     check_hosts=False,
                     pool=self._POOL).AndReturn(7)
        self.mox.ReplayAll()
        self.assertTrue(self.scheduler.ScheduleSuite(self._SUITE,
                                                     self._BOARD,
                                                     self._BUILD,
                                                     self._POOL))


    def testShouldNotScheduleSuite(self):
        """Test a successful de-dup and avoiding scheduling the suite."""
        # A similar suite has already been scheduled.
        self.afe.get_jobs(
            name__startswith=self._BUILD,
            name__endswith='control.'+self._SUITE).AndReturn(['42'])
        self.mox.ReplayAll()
        self.assertFalse(self.scheduler.ScheduleSuite(self._SUITE,
                                                      self._BOARD,
                                                      self._BUILD,
                                                      self._POOL))


    def testForceScheduleSuite(self):
        """Test a successful de-dup, but force scheduling the suite."""
        # Expect an attempt to schedule; allow it to succeed.
        self.afe.run('create_suite_job',
                     suite_name=self._SUITE,
                     board=self._BOARD,
                     build=self._BUILD,
                     check_hosts=False,
                     pool=self._POOL).AndReturn(7)
        self.mox.ReplayAll()
        self.assertTrue(self.scheduler.ScheduleSuite(self._SUITE,
                                                     self._BOARD,
                                                     self._BUILD,
                                                     self._POOL,
                                                     force=True))


    def testShouldScheduleSuiteExplodes(self):
        """Test a failure to de-dup."""
        # Barf while checking for similar suites.
        self.afe.get_jobs(
            name__startswith=self._BUILD,
            name__endswith='control.'+self._SUITE).AndRaise(Exception())
        self.mox.ReplayAll()
        self.assertRaises(deduping_scheduler.DedupException,
                          self.scheduler.ScheduleSuite,
                          self._SUITE,
                          self._BOARD,
                          self._BUILD,
                          self._POOL)


    def testScheduleFail(self):
        """Test a successful de-dup and failure to schedule the suite."""
        # A similar suite has not already been scheduled.
        self.afe.get_jobs(name__startswith=self._BUILD,
                          name__endswith='control.'+self._SUITE).AndReturn([])
        # Expect an attempt to create a job for the suite; fail it.
        self.afe.run('create_suite_job',
                     suite_name=self._SUITE,
                     board=self._BOARD,
                     build=self._BUILD,
                     check_hosts=False,
                     pool=None).AndReturn(None)
        self.mox.ReplayAll()
        self.assertRaises(deduping_scheduler.ScheduleException,
                          self.scheduler.ScheduleSuite,
                          self._SUITE,
                          self._BOARD,
                          self._BUILD,
                          None)


    def testScheduleExplodes(self):
        """Test a successful de-dup and barf while scheduling the suite."""
        # A similar suite has not already been scheduled.
        self.afe.get_jobs(name__startswith=self._BUILD,
                          name__endswith='control.'+self._SUITE).AndReturn([])
        # Expect an attempt to create a job for the suite; barf on it.
        self.afe.run('create_suite_job',
                     suite_name=self._SUITE,
                     board=self._BOARD,
                     build=self._BUILD,
                     check_hosts=False,
                     pool=None).AndRaise(Exception())
        self.mox.ReplayAll()
        self.assertRaises(deduping_scheduler.ScheduleException,
                          self.scheduler.ScheduleSuite,
                          self._SUITE,
                          self._BOARD,
                          self._BUILD,
                          None)


if __name__ == '__main__':
    unittest.main()
