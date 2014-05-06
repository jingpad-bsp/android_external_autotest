"""Autotest host scheduler.
"""

import collections
import logging

from autotest_lib.scheduler import query_managers
from autotest_lib.scheduler import rdb_lib
from autotest_lib.scheduler import rdb_utils
from autotest_lib.site_utils.graphite import stats


class BaseHostScheduler(object):
    """Base class containing host acquisition logic.

    This class contains all the core host acquisition logic needed by the
    scheduler to run jobs on hosts. It is only capable of releasing hosts
    back to the rdb through its tick, any other action must be instigated by
    the job scheduler.
    """


    _timer = stats.Timer('base_host_scheduler')
    host_assignment = collections.namedtuple('host_assignment', ['host', 'job'])


    def __init__(self):
        self.host_query_manager = query_managers.AFEHostQueryManager()


    @_timer.decorate
    def _release_hosts(self):
        """Release hosts to the RDB.

        Release all hosts that are ready and are currently not being used by an
        active hqe, and don't have a new special task scheduled against them.
        """
        release_hostnames = [host.hostname for host in
                             self.host_query_manager.find_unused_healty_hosts()]
        if release_hostnames:
            self.host_query_manager.set_leased(
                    False, hostname__in=release_hostnames)


    @classmethod
    def schedule_host_job(cls, host, queue_entry):
        """Schedule a job on a host.

        Scheduling a job involves:
            1. Setting the active bit on the queue_entry.
            2. Scheduling a special task on behalf of the queue_entry.
        Performing these actions will lead the job scheduler through a chain of
        events, culminating in running the test and collecting results from
        the host.

        @param host: The host against which to schedule the job.
        @param queue_entry: The queue_entry to schedule.
        """
        if queue_entry.host_id is None:
            queue_entry.set_host(host)
        elif host.id != queue_entry.host_id:
                raise rdb_utils.RDBException('The rdb returned host: %s '
                        'but the job:%s was already assigned a host: %s. ' %
                        (host.hostname, queue_entry.job_id,
                         queue_entry.host.hostname))
        queue_entry.update_field('active', True)

        # TODO: crbug.com/373936. The host scheduler should only be assigning
        # jobs to hosts, but the criterion we use to release hosts depends
        # on it not being used by an active hqe. Since we're activating the
        # hqe here, we also need to schedule its first prejob task. OTOH,
        # we could converge to having the host scheduler manager all special
        # tasks, since their only use today is to verify/cleanup/reset a host.
        logging.info('Scheduling pre job tasks for entry: %s', queue_entry)
        queue_entry.schedule_pre_job_tasks()


    @classmethod
    def find_hosts_for_jobs(cls, host_jobs):
        """Find and verify hosts for a list of jobs.

        @param host_jobs: A list of queue entries that either require hosts,
            or require host assignment validation through the rdb.
        @return: A list of tuples of the form (host, queue_entry) for each
            valid host-queue_entry assignment.
        """
        jobs_with_hosts = []
        hosts = rdb_lib.acquire_hosts(host_jobs)
        for host, job in zip(hosts, host_jobs):
            if host:
                jobs_with_hosts.append(cls.host_assignment(host, job))
        return jobs_with_hosts


    @_timer.decorate
    def tick(self):
        """Schedule core host management activities."""
        self._release_hosts()


class DummyHostScheduler(BaseHostScheduler):
    """A dummy host scheduler that doesn't acquire or release hosts."""

    def __init__(self):
        pass


    def tick(self):
        pass
