#!/usr/bin/python
#pylint: disable-msg=C0111

# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

import common

from autotest_lib.client.common_lib.test_utils import unittest
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.afe import frontend_test_utils
from autotest_lib.frontend.afe import models
from autotest_lib.scheduler import rdb
from autotest_lib.scheduler import rdb_lib
from autotest_lib.scheduler import rdb_testing_utils


class QueryManagerTests(rdb_testing_utils.AbstractBaseRDBTester,
                        unittest.TestCase):
    """Verify scheduler behavior when pending jobs are already given hosts."""

    _config_section = 'AUTOTEST_WEB'


    def testPendingQueueEntries(self):
        """Test retrieval of pending queue entries."""
        job = self.create_job(deps=set(['a']))

        # Check that we don't pull the job we just created with only_hostless.
        jobs_with_hosts = self.job_query_manager.get_pending_queue_entries(
                only_hostless=True)
        self.assertTrue(len(jobs_with_hosts) == 0)

        # Check that only_hostless=False pulls new jobs, as always.
        jobs_without_hosts = self.job_query_manager.get_pending_queue_entries(
                only_hostless=False)
        self.assertTrue(jobs_without_hosts[0].id == job.id and
                        jobs_without_hosts[0].host_id is None)


    def testHostQueries(self):
        """Verify that the host query manager maintains its data structures."""
        # Create a job and use the host_query_managers internal datastructures
        # to retrieve its job info.
        job = self.create_job(
                deps=rdb_testing_utils.DEFAULT_DEPS,
                acls=rdb_testing_utils.DEFAULT_ACLS)
        queue_entries = self._dispatcher._refresh_pending_queue_entries()
        job_manager = rdb_lib.JobQueryManager(queue_entries)
        job_info = job_manager.get_job_info(queue_entries[0])
        default_dep_ids = set([label.id for label in self.db_helper.get_labels(
                name__in=rdb_testing_utils.DEFAULT_DEPS)])
        default_acl_ids = set([acl.id for acl in self.db_helper.get_acls(
                name__in=rdb_testing_utils.DEFAULT_ACLS)])
        self.assertTrue(set(job_info['deps']) == default_dep_ids)
        self.assertTrue(set(job_info['acls']) == default_acl_ids)


    def testNewJobsWithHosts(self):
        """Test that we handle inactive hqes with unleased hosts correctly."""
        # Create a job and assign it an unleased host, then check that the
        # HQE becomes active and the host remains assigned to it.
        job = self.create_job(deps=['a'])
        host = self.db_helper.create_host('h1', deps=['a'])
        self.db_helper.add_host_to_job(host, job.id)

        queue_entries = self._dispatcher._refresh_pending_queue_entries()
        self._dispatcher._schedule_new_jobs()

        host = self.db_helper.get_host(hostname='h1')[0]
        self.assertTrue(host.leased == True and
                        host.status == models.Host.Status.READY)
        hqes = list(self.db_helper.get_hqes(host_id=host.id))
        self.assertTrue(len(hqes) == 1 and hqes[0].active and
                        hqes[0].status == models.HostQueueEntry.Status.QUEUED)


    def testNewJobsWithInvalidHost(self):
        """Test handling of inactive hqes assigned invalid, unleased hosts."""
        # Create a job and assign it an unleased host, then check that the
        # HQE becomes DOES NOT become active, because we validate the
        # assignment again.
        job = self.create_job(deps=['a'])
        host = self.db_helper.create_host('h1', deps=['b'])
        self.db_helper.add_host_to_job(host, job.id)

        queue_entries = self._dispatcher._refresh_pending_queue_entries()
        self._dispatcher._schedule_new_jobs()

        host = self.db_helper.get_host(hostname='h1')[0]
        self.assertTrue(host.leased == False and
                        host.status == models.Host.Status.READY)
        hqes = list(self.db_helper.get_hqes(host_id=host.id))
        self.assertTrue(len(hqes) == 1 and not hqes[0].active and
                        hqes[0].status == models.HostQueueEntry.Status.QUEUED)


    def testNewJobsWithLeasedHost(self):
        """Test handling of inactive hqes assigned leased hosts."""
        # Create a job and assign it a leased host, then check that the
        # HQE does not become active through the scheduler, and that the
        # host gets released.
        job = self.create_job(deps=['a'])
        host = self.db_helper.create_host('h1', deps=['b'])
        self.db_helper.add_host_to_job(host, job.id)
        host.leased = 1
        host.save()

        rdb.batch_acquire_hosts = mock.MagicMock()
        queue_entries = self._dispatcher._refresh_pending_queue_entries()
        self._dispatcher._schedule_new_jobs()
        self.assertTrue(rdb.batch_acquire_hosts.call_count == 0)
        host = self.db_helper.get_host(hostname='h1')[0]
        self.assertTrue(host.leased == True and
                        host.status == models.Host.Status.READY)
        hqes = list(self.db_helper.get_hqes(host_id=host.id))
        self.assertTrue(len(hqes) == 1 and not hqes[0].active and
                        hqes[0].status == models.HostQueueEntry.Status.QUEUED)
        self.host_scheduler._release_hosts()
        self.assertTrue(self.db_helper.get_host(hostname='h1')[0].leased == 0)


    def testSpecialTaskOrdering(self):
        """Test priority ordering of special tasks."""

        # Create 2 special tasks, one with and one without an hqe.
        # Then assign the same host to another active hqe and make
        # sure we don't try scheduling either of these special tasks.
        host = self.db_helper.create_host('h1', deps=['a'])
        task1 = self.db_helper.create_special_task(host_id=host.id)
        job = self.create_job(deps=['a'])
        self.db_helper.add_host_to_job(host, job.id)
        hqe = self.db_helper.get_hqes(job=job.id)[0]
        task2 = self.db_helper.create_special_task(job.id)
        tasks = self.job_query_manager.get_prioritized_special_tasks()
        self.assertTrue(tasks[0].queue_entry_id is None and
                        tasks[1].queue_entry_id == hqe.id)

        job2 = self.create_job(deps=['a'])
        self.db_helper.add_host_to_job(host, job2.id)
        hqe2 = self.db_helper.get_hqes(job=job2.id)[0]
        hqe2.status = models.HostQueueEntry.Status.RUNNING
        hqe2.save()
        tasks = self.job_query_manager.get_prioritized_special_tasks()
        self.assertTrue(tasks == [])


