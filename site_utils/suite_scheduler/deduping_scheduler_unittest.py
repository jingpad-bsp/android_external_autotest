#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for site_utils/deduping_scheduler.py."""

import mox
import unittest

import common
import deduping_scheduler

from autotest_lib.client.common_lib import error
from autotest_lib.server import frontend, site_utils
from autotest_lib.server.cros.dynamic_suite import reporting


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
    _NUM = 2


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
                     pool=self._POOL,
                     num=self._NUM).AndReturn(7)
        self.mox.ReplayAll()
        self.assertTrue(self.scheduler.ScheduleSuite(self._SUITE,
                                                     self._BOARD,
                                                     self._BUILD,
                                                     self._POOL,
                                                     self._NUM))


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
                                                      self._POOL,
                                                      None))


    def testForceScheduleSuite(self):
        """Test a successful de-dup, but force scheduling the suite."""
        # Expect an attempt to schedule; allow it to succeed.
        self.afe.run('create_suite_job',
                     suite_name=self._SUITE,
                     board=self._BOARD,
                     build=self._BUILD,
                     check_hosts=False,
                     num=None,
                     pool=self._POOL).AndReturn(7)
        self.mox.ReplayAll()
        self.assertTrue(self.scheduler.ScheduleSuite(self._SUITE,
                                                     self._BOARD,
                                                     self._BUILD,
                                                     self._POOL,
                                                     None,
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
                          self._POOL,
                          self._NUM)


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
                     num=None,
                     pool=None).AndReturn(None)
        self.mox.ReplayAll()
        self.assertRaises(deduping_scheduler.ScheduleException,
                          self.scheduler.ScheduleSuite,
                          self._SUITE,
                          self._BOARD,
                          self._BUILD,
                          None,
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
                     num=None,
                     pool=None).AndRaise(Exception())
        self.mox.ReplayAll()
        self.assertRaises(deduping_scheduler.ScheduleException,
                          self.scheduler.ScheduleSuite,
                          self._SUITE,
                          self._BOARD,
                          self._BUILD,
                          None,
                          None)


    def testScheduleReportsBug(self):
        """Test that the scheduler file a bug for ControlFileNotFound."""
        self.mox.StubOutWithMock(reporting.Reporter, '__init__')
        self.mox.StubOutWithMock(reporting.Reporter, 'create_bug_report')
        self.mox.StubOutWithMock(site_utils, 'get_sheriffs')
        self.mox.StubOutClassWithMocks(reporting, 'Bug')
        self.scheduler._file_bug = True
        # A similar suite has not already been scheduled.
        self.afe.get_jobs(name__startswith=self._BUILD,
                          name__endswith='control.'+self._SUITE).AndReturn([])
        message = 'Control file not found.'
        exception = error.ControlFileNotFound(message)
        self.afe.run('create_suite_job',
                     suite_name=self._SUITE,
                     board=self._BOARD,
                     build=self._BUILD,
                     check_hosts=False,
                     pool=self._POOL,
                     num=self._NUM).AndRaise(exception)
        reporting.Reporter.__init__()
        title = ('Exception "%s" occurs when scheduling %s on '
                 '%s against %s (pool: %s)' %
                 (exception.__class__.__name__,
                  self._SUITE, self._BUILD, self._BOARD, self._POOL))
        site_utils.get_sheriffs(
                lab_only=True).AndReturn(['dummy@chromium.org'])
        bug = reporting.Bug(title=title,
                            summary=mox.IgnoreArg(),
                            owner='dummy@chromium.org')
        reporting.Reporter.create_bug_report(
                bug,
                bug_template = {'labels': ['Suite-Scheduler-Bug'],
                                'status': 'Available'},
                sheriffs=[]).AndReturn(1158)
        self.mox.ReplayAll()
        self.assertFalse(self.scheduler.ScheduleSuite(self._SUITE,
                                                     self._BOARD,
                                                     self._BUILD,
                                                     self._POOL,
                                                     self._NUM))
        self.mox.VerifyAll()


if __name__ == '__main__':
    unittest.main()
