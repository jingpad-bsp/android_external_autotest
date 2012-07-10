#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for server/cros/job_status.py."""

import logging
import mox
import shutil
import tempfile
import time
import unittest

from autotest_lib.server.cros import job_status, host_lock_manager
from autotest_lib.server.cros.dynamic_suite_fakes import FakeHost, FakeJob
from autotest_lib.server.cros.dynamic_suite_fakes import FakeStatus
from autotest_lib.server import frontend


class StatusTest(mox.MoxTestBase):
    """Unit tests for job_status.Status.
    """


    def setUp(self):
        super(StatusTest, self).setUp()
        self.afe = self.mox.CreateMock(frontend.AFE)
        self.tko = self.mox.CreateMock(frontend.TKO)

        self.tmpdir = tempfile.mkdtemp(suffix=type(self).__name__)


    def tearDown(self):
        super(StatusTest, self).tearDown()
        shutil.rmtree(self.tmpdir, ignore_errors=True)


    def testGatherJobHostnamesAllRan(self):
        """All entries for the job were assigned hosts."""
        job = FakeJob(0, [])
        expected_hosts = ['host2', 'host1']
        entries = [{'host': {'hostname': h}} for h in expected_hosts]
        self.afe.run('get_host_queue_entries', job=job.id).AndReturn(entries)
        self.mox.ReplayAll()

        self.assertEquals(sorted(expected_hosts),
                          sorted(job_status.gather_job_hostnames(self.afe,
                                                                 job)))


    def testGatherJobHostnamesSomeRan(self):
        """Not all entries for the job were assigned hosts."""
        job = FakeJob(0, [])
        expected_hosts = ['host2', 'host1']
        entries = [{'host': {'hostname': h}} for h in expected_hosts]
        entries.append({'host': None})
        self.afe.run('get_host_queue_entries', job=job.id).AndReturn(entries)
        self.mox.ReplayAll()

        self.assertEquals(sorted(expected_hosts),
                          sorted(job_status.gather_job_hostnames(self.afe,
                                                                 job)))


    def testWaitForJobToStart(self):
        """Ensure we detect when a job has started running."""
        self.mox.StubOutWithMock(time, 'sleep')

        job = FakeJob(0, [])
        self.afe.get_jobs(id=job.id, not_yet_run=True).AndReturn([job])
        self.afe.get_jobs(id=job.id, not_yet_run=True).AndReturn([])
        time.sleep(mox.IgnoreArg()).MultipleTimes()
        self.mox.ReplayAll()

        job_status.wait_for_job_to_start(self.afe, job)


    def testWaitForJobToStartAlreadyStarted(self):
        """Ensure we don't wait forever if a job already started."""
        job = FakeJob(0, [])
        self.afe.get_jobs(id=job.id, not_yet_run=True).AndReturn([])
        self.mox.ReplayAll()
        job_status.wait_for_job_to_start(self.afe, job)


    def testWaitForJobToFinish(self):
        """Ensure we detect when a job has finished."""
        self.mox.StubOutWithMock(time, 'sleep')

        job = FakeJob(0, [])
        self.afe.get_jobs(id=job.id, finished=True).AndReturn([])
        self.afe.get_jobs(id=job.id, finished=True).AndReturn([job])
        time.sleep(mox.IgnoreArg()).MultipleTimes()
        self.mox.ReplayAll()

        job_status.wait_for_job_to_finish(self.afe, job)


    def testWaitForJobToStartAlreadyFinished(self):
        """Ensure we don't wait forever if a job already finished."""
        job = FakeJob(0, [])
        self.afe.get_jobs(id=job.id, finished=True).AndReturn([job])
        self.mox.ReplayAll()
        job_status.wait_for_job_to_finish(self.afe, job)


    def testWaitForJobHostsToRunAndGetLocked(self):
        """Ensure we lock all running hosts as they're discovered."""
        self.mox.StubOutWithMock(time, 'sleep')

        job = FakeJob(0, [])
        manager = self.mox.CreateMock(host_lock_manager.HostLockManager)
        expected_hosts = [FakeHost('host2'), FakeHost('host1')]
        expected_hostnames = [h.hostname for h in expected_hosts]
        entries = [{'host': {'hostname': h}} for h in expected_hostnames]

        time.sleep(mox.IgnoreArg()).MultipleTimes()
        self.afe.run('get_host_queue_entries', job=job.id).AndReturn(entries)

        self.afe.get_hosts(mox.SameElementsAs(expected_hostnames),
                           status='Running').AndReturn(expected_hosts[1:])
        manager.add(expected_hostnames[1:]).InAnyOrder('manager1')
        manager.lock().InAnyOrder('manager1')

        # Returning the same list of hosts more than once should be a noop.
        self.afe.get_hosts(mox.SameElementsAs(expected_hostnames),
                           status='Running').AndReturn(expected_hosts[1:])

        self.afe.get_hosts(mox.SameElementsAs(expected_hostnames),
                           status='Running').AndReturn(expected_hosts)
        manager.lock().InAnyOrder('manager2')
        manager.add(expected_hostnames).InAnyOrder('manager2')

        self.mox.ReplayAll()
        self.assertEquals(
            sorted(expected_hostnames),
            sorted(job_status.wait_for_and_lock_job_hosts(self.afe,
                                                          job,
                                                          manager)))


    def expect_result_gathering(self, job):
        self.afe.get_jobs(id=job.id, finished=True).AndReturn(job)
        entries = [s.entry for s in job.statuses]
        self.afe.run('get_host_queue_entries',
                     job=job.id).AndReturn(entries)
        if True not in map(lambda e: 'aborted' in e and e['aborted'], entries):
            self.tko.get_status_counts(job=job.id).AndReturn(job.statuses)


    def testWaitForResults(self):
        """Should gather status and return records for job summaries."""
        jobs = [FakeJob(0, [FakeStatus('GOOD', 'T0', ''),
                            FakeStatus('GOOD', 'T1', '')]),
                FakeJob(1, [FakeStatus('ERROR', 'T0', 'err', False),
                            FakeStatus('GOOD', 'T1', '')]),
                FakeJob(2, [FakeStatus('TEST_NA', 'T0', 'no')]),
                FakeJob(3, [FakeStatus('FAIL', 'T0', 'broken')]),
                FakeJob(4, [FakeStatus('ERROR', 'T0', 'gah', True)])]
        # To simulate a job that isn't ready the first time we check.
        self.afe.get_jobs(id=jobs[0].id, finished=True).AndReturn([])
        # Expect all the rest of the jobs to be good to go the first time.
        for job in jobs[1:]:
            self.expect_result_gathering(job)
        # Then, expect job[0] to be ready.
        self.expect_result_gathering(jobs[0])
        # Expect us to poll twice.
        self.mox.StubOutWithMock(time, 'sleep')
        time.sleep(5)
        time.sleep(5)
        self.mox.ReplayAll()

        results = [result for result in job_status.wait_for_results(self.afe,
                                                                    self.tko,
                                                                    jobs)]
        for job in jobs:
            for status in job.statuses:
                self.assertTrue(True in map(status.equals_record, results))


    def testGatherPerHostResults(self):
        """Should gather per host results."""
        # For the 0th job, the 1st entry is more bad/specific.
        # For all the others, it's the 0th that we expect.
        jobs = [FakeJob(0, [FakeStatus('FAIL', 'T0', '', hostname='h0'),
                            FakeStatus('FAIL', 'T1', 'bad', hostname='h0')]),
                FakeJob(1, [FakeStatus('ERROR', 'T0', 'err', False, 'h1'),
                            FakeStatus('GOOD', 'T1', '', hostname='h1')]),
                FakeJob(2, [FakeStatus('TEST_NA', 'T0', 'no', hostname='h2')]),
                FakeJob(3, [FakeStatus('FAIL', 'T0', 'broken', hostname='h3')]),
                FakeJob(4, [FakeStatus('ERROR', 'T0', 'gah', True, 'h4')]),
                FakeJob(5, [FakeStatus('GOOD', 'T0', 'Yay', hostname='h5')])]
        # Method under test returns status available right now.
        for job in jobs:
            entries = map(lambda s: s.entry, job.statuses)
            self.afe.run('get_host_queue_entries',
                         job=job.id).AndReturn(entries)
            self.tko.get_status_counts(job=job.id).AndReturn(job.statuses)
        self.mox.ReplayAll()

        results = job_status.gather_per_host_results(self.afe,
                                                     self.tko,
                                                     jobs).values()
        for status in [jobs[0].statuses[1]] + [j.statuses[0] for j in jobs[1:]]:
            self.assertTrue(True in map(status.equals_hostname_record, results))
