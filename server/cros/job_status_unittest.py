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

        self.assertEquals(sorted(expected_hosts + [None]),
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

        job_status.wait_for_jobs_to_start(self.afe, [job])


    def testWaitForMultipleJobsToStart(self):
        """Ensure we detect when all jobs have started running."""
        self.mox.StubOutWithMock(time, 'sleep')

        job0 = FakeJob(0, [])
        job1 = FakeJob(1, [])
        self.afe.get_jobs(id=job0.id, not_yet_run=True).AndReturn([job0])
        self.afe.get_jobs(id=job1.id, not_yet_run=True).AndReturn([job1])
        self.afe.get_jobs(id=job0.id, not_yet_run=True).AndReturn([])
        self.afe.get_jobs(id=job1.id, not_yet_run=True).AndReturn([job1])
        self.afe.get_jobs(id=job1.id, not_yet_run=True).AndReturn([])
        time.sleep(mox.IgnoreArg()).MultipleTimes()
        self.mox.ReplayAll()

        job_status.wait_for_jobs_to_start(self.afe, [job0, job1])


    def testWaitForJobToStartAlreadyStarted(self):
        """Ensure we don't wait forever if a job already started."""
        job = FakeJob(0, [])
        self.afe.get_jobs(id=job.id, not_yet_run=True).AndReturn([])
        self.mox.ReplayAll()
        job_status.wait_for_jobs_to_start(self.afe, [job])


    def testWaitForJobToFinish(self):
        """Ensure we detect when a job has finished."""
        self.mox.StubOutWithMock(time, 'sleep')

        job = FakeJob(0, [])
        self.afe.get_jobs(id=job.id, finished=True).AndReturn([])
        self.afe.get_jobs(id=job.id, finished=True).AndReturn([job])
        time.sleep(mox.IgnoreArg()).MultipleTimes()
        self.mox.ReplayAll()

        job_status.wait_for_jobs_to_finish(self.afe, [job])


    def testWaitForMultipleJobsToFinish(self):
        """Ensure we detect when all jobs have stopped running."""
        self.mox.StubOutWithMock(time, 'sleep')

        job0 = FakeJob(0, [])
        job1 = FakeJob(1, [])
        self.afe.get_jobs(id=job0.id, finished=True).AndReturn([])
        self.afe.get_jobs(id=job1.id, finished=True).AndReturn([])
        self.afe.get_jobs(id=job0.id, finished=True).AndReturn([])
        self.afe.get_jobs(id=job1.id, finished=True).AndReturn([job1])
        self.afe.get_jobs(id=job0.id, finished=True).AndReturn([job0])
        time.sleep(mox.IgnoreArg()).MultipleTimes()
        self.mox.ReplayAll()

        job_status.wait_for_jobs_to_finish(self.afe, [job0, job1])


    def testWaitForJobToFinishAlreadyFinished(self):
        """Ensure we don't wait forever if a job already finished."""
        job = FakeJob(0, [])
        self.afe.get_jobs(id=job.id, finished=True).AndReturn([job])
        self.mox.ReplayAll()
        job_status.wait_for_jobs_to_finish(self.afe, [job])


    def expect_hosts_query_and_lock(self, jobs, manager, running_hosts,
                                    do_lock=True):
        """Expect asking for a job's hosts and, potentially, lock them.

        job_status.gather_job_hostnames() should be mocked out prior to call.

        @param jobs: a lists of FakeJobs with a valid ID.
        @param manager: mocked out HostLockManager
        @param running_hosts: list of FakeHosts that should be listed as
                              'Running'.
        @param do_lock: If |manager| should expect |running_hosts| to get
                        added and locked.
        @return nothing, but self.afe, job_status.gather_job_hostnames, and
                manager will have expectations set.
        """
        used_hostnames = []
        for job in jobs:
            job_status.gather_job_hostnames(
                    mox.IgnoreArg(), job).InAnyOrder().AndReturn(job.hostnames)
            used_hostnames.extend([h for h in job.hostnames if h])

        if used_hostnames:
            self.afe.get_hosts(mox.SameElementsAs(used_hostnames),
                               status='Running').AndReturn(running_hosts)
        if do_lock:
            manager.add([h.hostname for h in running_hosts])
            manager.lock()


    def testWaitForSingleJobHostsToRunAndGetLocked(self):
        """Ensure we lock all running hosts as they're discovered."""
        self.mox.StubOutWithMock(time, 'sleep')
        self.mox.StubOutWithMock(job_status, 'gather_job_hostnames')

        manager = self.mox.CreateMock(host_lock_manager.HostLockManager)
        expected_hostnames=['host1', 'host0']
        expected_hosts = [FakeHost(h) for h in expected_hostnames]
        job = FakeJob(7, hostnames=[None, None])

        time.sleep(mox.IgnoreArg()).MultipleTimes()
        self.expect_hosts_query_and_lock([job], manager, [], False)
        # First, only one test in the job has had a host assigned at all.
        # Since no hosts are running, expect no locking.
        job.hostnames = [None] + expected_hostnames[1:]
        self.expect_hosts_query_and_lock([job], manager, [], False)

        # Then, that host starts running, but no other tests have hosts.
        self.expect_hosts_query_and_lock([job], manager, expected_hosts[1:])

        # The second test gets a host assigned, but it's not yet running.
        # Since no new running hosts are found, no locking should happen.
        job.hostnames = expected_hostnames
        self.expect_hosts_query_and_lock([job], manager, expected_hosts[1:],
                                         False)
        # The second test's host starts running as well.
        self.expect_hosts_query_and_lock([job], manager, expected_hosts)

        # The last loop update; doesn't impact behavior.
        job_status.gather_job_hostnames(mox.IgnoreArg(),
                                        job).AndReturn(expected_hostnames)
        self.mox.ReplayAll()
        self.assertEquals(
            sorted(expected_hostnames),
            sorted(job_status.wait_for_and_lock_job_hosts(self.afe,
                                                          [job],
                                                          manager)))


    def testWaitForMultiJobHostsToRunAndGetLocked(self):
        """Ensure we lock all running hosts for all jobs as discovered."""
        self.mox.StubOutWithMock(time, 'sleep')
        self.mox.StubOutWithMock(job_status, 'gather_job_hostnames')

        manager = self.mox.CreateMock(host_lock_manager.HostLockManager)
        expected_hostnames = ['host1', 'host0', 'host2']
        expected_hosts = [FakeHost(h) for h in expected_hostnames]
        job0 = FakeJob(0, hostnames=[])
        job1 = FakeJob(1, hostnames=[])

        time.sleep(mox.IgnoreArg()).MultipleTimes()
        # First, only one test in either job has had a host assigned at all.
        # Since no hosts are running, expect no locking.
        job0.hostnames = [None, expected_hostnames[2]]
        job1.hostnames = [None]
        self.expect_hosts_query_and_lock([job0, job1], manager, [], False)

        # Then, that host starts running, but no other tests have hosts.
        self.expect_hosts_query_and_lock([job0, job1], manager,
                                         expected_hosts[2:])

        # The test in the second job gets a host assigned, but it's not yet
        # running.
        # Since no new running hosts are found, no locking should happen.
        job1.hostnames = expected_hostnames[1:2]
        self.expect_hosts_query_and_lock([job0, job1], manager,
                                         expected_hosts[2:], False)

        # The second job's test's host starts running as well.
        self.expect_hosts_query_and_lock([job0, job1], manager,
                                         expected_hosts[1:])

        # All three hosts across both jobs are now running.
        job0.hostnames = [expected_hostnames[0], expected_hostnames[2]]
        self.expect_hosts_query_and_lock([job0, job1], manager, expected_hosts)

        # The last loop update; doesn't impact behavior.
        job_status.gather_job_hostnames(mox.IgnoreArg(),
                                        job0).AndReturn(job0.hostnames)
        job_status.gather_job_hostnames(mox.IgnoreArg(),
                                        job1).AndReturn(job1.hostnames)

        self.mox.ReplayAll()
        self.assertEquals(
            sorted(expected_hostnames),
            sorted(job_status.wait_for_and_lock_job_hosts(self.afe,
                                                          [job0, job1],
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
                FakeJob(4, [FakeStatus('ERROR', 'SERVER_JOB', 'server error'),
                            FakeStatus('GOOD', 'T0', '')]),
                FakeJob(5, [FakeStatus('ERROR', 'T0', 'gah', True)]),
                # The next job shouldn't be recorded in the results.
                FakeJob(6, [FakeStatus('GOOD', 'SERVER_JOB', '')])]
        for status in jobs[4].statuses:
            status.entry['job'] = {'name': 'broken_infra_job'}

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
        for job in jobs[:6]:  # the 'GOOD' SERVER_JOB shouldn't be there.
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
