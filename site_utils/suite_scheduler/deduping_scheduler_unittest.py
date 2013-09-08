#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for site_utils/deduping_scheduler.py."""

import mox
import unittest

# driver must be imported first due to circular imports in base_event and task
import driver  # pylint: disable-msg=W0611
import deduping_scheduler

import common
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import priorities
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
    _PRIORITY = priorities.Priority.POSTBUILD
    _TIMEOUT = 24


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
                     num=self._NUM,
                     priority=self._PRIORITY,
                     timeout=self._TIMEOUT).AndReturn(7)
        self.mox.ReplayAll()
        self.assertTrue(self.scheduler.ScheduleSuite(self._SUITE,
                                                     self._BOARD,
                                                     self._BUILD,
                                                     self._POOL,
                                                     self._NUM,
                                                     self._PRIORITY,
                                                     self._TIMEOUT))


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
                                                      None,
                                                      self._PRIORITY,
                                                      self._TIMEOUT))


    def testForceScheduleSuite(self):
        """Test a successful de-dup, but force scheduling the suite."""
        # Expect an attempt to schedule; allow it to succeed.
        self.afe.run('create_suite_job',
                     suite_name=self._SUITE,
                     board=self._BOARD,
                     build=self._BUILD,
                     check_hosts=False,
                     num=None,
                     pool=self._POOL,
                     priority=self._PRIORITY,
                     timeout=self._TIMEOUT).AndReturn(7)
        self.mox.ReplayAll()
        self.assertTrue(self.scheduler.ScheduleSuite(self._SUITE,
                                                     self._BOARD,
                                                     self._BUILD,
                                                     self._POOL,
                                                     None,
                                                     self._PRIORITY,
                                                     self._TIMEOUT,
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
                          self._NUM,
                          self._PRIORITY,
                          self._TIMEOUT)


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
                     pool=None,
                     priority=self._PRIORITY,
                     timeout=self._TIMEOUT).AndReturn(None)
        self.mox.ReplayAll()
        self.assertRaises(deduping_scheduler.ScheduleException,
                          self.scheduler.ScheduleSuite,
                          self._SUITE,
                          self._BOARD,
                          self._BUILD,
                          None,
                          None,
                          self._PRIORITY,
                          self._TIMEOUT)


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
                     pool=None,
                     priority=self._PRIORITY,
                     timeout=self._TIMEOUT).AndRaise(Exception())
        self.mox.ReplayAll()
        self.assertRaises(deduping_scheduler.ScheduleException,
                          self.scheduler.ScheduleSuite,
                          self._SUITE,
                          self._BOARD,
                          self._BUILD,
                          None,
                          None,
                          self._PRIORITY,
                          self._TIMEOUT)


    def testScheduleReportsBug(self):
        """Test that the scheduler file a bug for ControlFileNotFound."""
        self.mox.StubOutWithMock(reporting.Reporter, '__init__')
        self.mox.StubOutWithMock(reporting.Reporter, '_create_bug_report')
        self.mox.StubOutWithMock(reporting.Reporter, '_check_tracker')
        self.mox.StubOutWithMock(site_utils, 'get_sheriffs')
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
                     num=self._NUM,
                     priority=self._PRIORITY,
                     timeout=self._TIMEOUT).AndRaise(exception)
        site_utils.get_sheriffs(
                lab_only=True).AndReturn(['dummy@chromium.org'])
        # mox does not raise an AttributeError when a nonexistent attribute
        # is accessed. Doing this odd mocking out allows us to both have a
        # real Bug instance (so AttributeError is raised) while also letting
        # check for the arguments being passed into _create_bug_report work.
        title = ('Exception "%s" occurs when scheduling %s on '
                 '%s against %s (pool: %s)' %
                 (exception.__class__.__name__,
                  self._SUITE, self._BUILD, self._BOARD, self._POOL))
        bug = reporting.Bug(title=title,
                            summary='IGNORED',
                            owner='dummy@chromium.org',
                            labels=['Suite-Scheduler-Bug'])
        self.mox.StubOutWithMock(reporting, 'Bug')
        reporting.Bug(title=title,
                      summary=mox.IgnoreArg(),
                      owner='dummy@chromium.org',
                      labels=['Suite-Scheduler-Bug']).AndReturn(bug)

        reporting.Reporter.__init__()
        reporting.Reporter._check_tracker().AndReturn(True)
        reporting.Reporter._create_bug_report(bug, {}, []).AndReturn(1158)
        self.mox.ReplayAll()
        self.assertFalse(self.scheduler.ScheduleSuite(self._SUITE,
                                                     self._BOARD,
                                                     self._BUILD,
                                                     self._POOL,
                                                     self._NUM,
                                                     self._PRIORITY,
                                                     self._TIMEOUT))
        self.mox.VerifyAll()


if __name__ == '__main__':
    unittest.main()
