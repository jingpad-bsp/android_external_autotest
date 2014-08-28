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
from autotest_lib.scheduler import email_manager
from autotest_lib.scheduler import host_scheduler
from autotest_lib.scheduler import monitor_db
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


    def testPendingQueueEntriesForShard(self):
        """Test queue entries for shards aren't executed by master scheduler"""
        job1 = self.create_job(deps=set(['a']))
        job2 = self.create_job(deps=set(['b']))
        shard = models.Shard.objects.create()
        # Assign the job's label to a shard
        shard.labels.add(job1.dependency_labels.all()[0])

        # Check that we only pull jobs which are not assigned to a shard.
        jobs_with_hosts = self.job_query_manager.get_pending_queue_entries()
        self.assertTrue(len(jobs_with_hosts) == 1)
        self.assertEqual(jobs_with_hosts[0].id, job2.id)


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
        # Activate the hqe and make sure it gets scheduled before the other.
        host = self.db_helper.create_host('h1', deps=['a'])
        job1 = self.create_job(deps=['a'])
        self.db_helper.add_host_to_job(host, job1.id)
        task1 = self.db_helper.create_special_task(job1.id)
        hqe = self.db_helper.get_hqes(job=job1.id)[0]

        # This task has no queue entry.
        task2 = self.db_helper.create_special_task(host_id=host.id)

        # Since the hqe task isn't active we get both back.
        tasks = self.job_query_manager.get_prioritized_special_tasks()
        self.assertTrue(tasks[1].queue_entry_id is None and
                        tasks[0].queue_entry_id == hqe.id)

        # Activate the hqe and make sure the frontned task isn't returned.
        self.db_helper.update_hqe(hqe.id, active=True)
        tasks = self.job_query_manager.get_prioritized_special_tasks()
        self.assertTrue(tasks[0].id == task1.id)


class HostSchedulerTests(rdb_testing_utils.AbstractBaseRDBTester,
                         unittest.TestCase):
    """Verify scheduler behavior when pending jobs are already given hosts."""

    _config_section = 'AUTOTEST_WEB'


    def setUp(self):
        super(HostSchedulerTests, self).setUp()
        self.host_scheduler = host_scheduler.HostScheduler()


    def testSpecialTaskLocking(self):
        """Test that frontend special tasks lock hosts."""
        # Create multiple tasks with hosts and make sure the hosts get locked.
        host = self.db_helper.create_host('h')
        host1 = self.db_helper.create_host('h1')
        task = self.db_helper.create_special_task(host_id=host.id)
        task1 = self.db_helper.create_special_task(host_id=host1.id)
        self.host_scheduler._lease_hosts_of_frontend_tasks()
        self.assertTrue(self.db_helper.get_host(hostname='h')[0].leased == 1 and
                        self.db_helper.get_host(hostname='h1')[0].leased == 1)


    def testJobScheduling(self):
        """Test new host acquisitions."""
        # Create a job that will find a host through the host scheduler, and
        # make sure the hqe is activated, and a special task is created.
        job = self.create_job(deps=set(['a']))
        host = self.db_helper.create_host('h1', deps=set(['a']))
        self.host_scheduler._schedule_jobs()
        hqe = self.db_helper.get_hqes(job_id=job.id)[0]
        self.assertTrue(hqe.active and hqe.host_id == host.id and
                        hqe.status == models.HostQueueEntry.Status.QUEUED)
        task = self.db_helper.get_tasks(queue_entry_id=hqe.id)[0]
        self.assertTrue(task.is_active == 0 and task.host_id == host.id)


    def testOverlappingJobs(self):
        """Check that we catch all cases of an overlapping job."""
        job_1 =  self.create_job(deps=set(['a']))
        job_2 =  self.create_job(deps=set(['a']))
        host = self.db_helper.create_host('h1', deps=set(['a']))
        self.db_helper.add_host_to_job(host, job_1.id, activate=True)
        self.db_helper.add_host_to_job(host, job_2.id, activate=True)
        jobs = (self.host_scheduler.job_query_manager.get_overlapping_jobs())
        self.assertTrue(len(jobs) == 2 and
                        jobs[0]['host_id'] == jobs[1]['host_id'])
        email_manager.manager.enqueue_notify_email = mock.MagicMock()
        self.host_scheduler._check_host_assignments()
        self.assertTrue(
                email_manager.manager.enqueue_notify_email.call_count == 1)


    def _check_agent_invariants(self, host, agent):
        host_agents = list(self._dispatcher._host_agents[host.id])
        self.assertTrue(len(host_agents) == 1)
        self.assertTrue(host_agents[0].task.task.id == agent.id)
        return host_agents[0]


    def testLeasedFrontendTaskHost(self):
        """Check that we don't scheduler a special task on an unleased host."""
        # Create a special task without an hqe and make sure it isn't returned
        # for scheduling till its host is leased.
        host = self.db_helper.create_host('h1', deps=['a'])
        task = self.db_helper.create_special_task(host_id=host.id)

        tasks = self.job_query_manager.get_prioritized_special_tasks(
                only_tasks_with_leased_hosts=True)
        self.assertTrue(tasks == [])
        tasks = self.job_query_manager.get_prioritized_special_tasks(
                only_tasks_with_leased_hosts=False)
        self.assertTrue(tasks[0].id == task.id)
        self.host_scheduler._lease_hosts_of_frontend_tasks()
        tasks = self.job_query_manager.get_prioritized_special_tasks(
                only_tasks_with_leased_hosts=True)
        self.assertTrue(tasks[0].id == task.id)


    def testTickLockStep(self):
        """Check that a frontend task and an hqe never run simultaneously."""

        self.god.stub_with(monitor_db, '_inline_host_acquisition', False)

        # Create a frontend special task against a host.
        host = self.db_helper.create_host('h1', deps=set(['a']))
        frontend_task = self.db_helper.create_special_task(host_id=host.id)
        self._dispatcher._schedule_special_tasks()
        # The frontend special task shouldn't get scheduled on the host till
        # the host is leased.
        self.assertFalse(self._dispatcher.host_has_agent(host))

        # Create a job for the same host and make the host scheduler lease the
        # host out to that job.
        job =  self.create_job(deps=set(['a']))
        self.host_scheduler._schedule_jobs()
        hqe = self.db_helper.get_hqes(job_id=job.id)[0]
        tasks = self.job_query_manager.get_prioritized_special_tasks(
                only_tasks_with_leased_hosts=True)
        # We should not find the frontend special task, even though its host is
        # now leased, because its leased by an active hqe.
        self.assertTrue(len(tasks) == 1 and tasks[0].queue_entry_id == hqe.id)
        self._dispatcher._schedule_special_tasks()
        self.assertTrue(self._dispatcher.host_has_agent(host))

        # Deactivate the hqe task and make sure the frontend task gets the host.
        task = tasks[0]
        self._dispatcher.remove_agent(self._check_agent_invariants(host, task))
        task.is_complete = 1
        task.is_active = 0
        task.save()
        self.db_helper.update_hqe(hqe.id, active=False)
        self._dispatcher._schedule_special_tasks()
        self.assertTrue(self._dispatcher.host_has_agent(host))
        self._check_agent_invariants(host, frontend_task)

        # Make sure we don't release the host being used by the incomplete task.
        self.host_scheduler._release_hosts()
        host = self.db_helper.get_host(hostname='h1')[0]
        self.assertTrue(host.leased == True)

