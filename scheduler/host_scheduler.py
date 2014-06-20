#!/usr/bin/python
#pylint: disable-msg=C0111

# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Host scheduler.

If run as a standalone service, the host scheduler ensures the following:
    1. Hosts will not be assigned to multiple hqes simultaneously. The process
       of assignment in this case refers to the modification of the host_id
       column of a row in the afe_host_queue_entries table, to reflect the host
       id of a leased host matching the dependencies of the job.
    2. Hosts that are not being used by active hqes or incomplete special tasks
       will be released back to the available hosts pool, for acquisition by
       subsequent hqes.
In addition to these guarantees, the host scheduler also confirms that no 2
active hqes/special tasks are assigned the same host, and sets the leased bit
for hosts needed by frontend special tasks. The need for the latter is only
apparent when viewed in the context of the job-scheduler (monitor_db), which
runs special tasks only after their hosts have been leased.
"""

import argparse
import collections
import logging
import os
import signal
import sys
import time

import common
from autotest_lib.frontend import setup_django_environment

from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.cros.graphite import stats
from autotest_lib.scheduler import email_manager
from autotest_lib.scheduler import query_managers
from autotest_lib.scheduler import rdb_lib
from autotest_lib.scheduler import rdb_utils
from autotest_lib.scheduler import scheduler_lib
from autotest_lib.scheduler import scheduler_models

_db_manager = None
_shutdown = False
_tick_pause_sec = global_config.global_config.get_config_value(
        'SCHEDULER', 'tick_pause_sec', type=int, default=5)
_monitor_db_host_acquisition = global_config.global_config.get_config_value(
        'SCHEDULER', 'inline_host_acquisition', type=bool, default=True)


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


class HostScheduler(BaseHostScheduler):
    """A scheduler capable managing host acquisition for new jobs."""

    _timer = stats.Timer('host_scheduler')


    def __init__(self):
        super(HostScheduler, self).__init__()
        self.job_query_manager = query_managers.AFEJobQueryManager()


    @_timer.decorate
    def _schedule_jobs(self):
        """Schedule new jobs against hosts."""
        queue_entries = self.job_query_manager.get_pending_queue_entries(
                only_hostless=False)
        unverified_host_jobs = [job for job in queue_entries
                                if not job.is_hostless()]
        if not unverified_host_jobs:
            return
        for acquisition in self.find_hosts_for_jobs(unverified_host_jobs):
            self.schedule_host_job(acquisition.host, acquisition.job)


    @_timer.decorate
    def _lease_hosts_of_frontend_tasks(self):
        """Lease hosts of tasks scheduled through the frontend."""
        # We really don't need to get all the special tasks here, just the ones
        # without hqes, but reusing the method used by the scheduler ensures
        # we prioritize the same way.
        lease_hostnames = [
                task.host.hostname for task in
                self.job_query_manager.get_prioritized_special_tasks(
                    only_tasks_with_leased_hosts=False)
                if task.queue_entry_id is None and not task.host.leased]
        # Leasing a leased hosts here shouldn't be a problem:
        # 1. The only way a host can be leased is if it's been assigned to
        #    an active hqe or another similar frontend task, but doing so will
        #    have already precluded it from the list of tasks returned by the
        #    job_query_manager.
        # 2. The unleasing is done based on global conditions. Eg: Even if a
        #    task has already leased a host and we lease it again, the
        #    host scheduler won't release the host till both tasks are complete.
        if lease_hostnames:
            self.host_query_manager.set_leased(
                    True, hostname__in=lease_hostnames)


    @_timer.decorate
    def _check_host_assignments(self):
        """Sanity check the current host assignments."""
        # Move this into a periodic cleanup if pressed for performance.
        message = ''
        subject = 'Unexpected host assignments'
        for offending_job in self.job_query_manager.get_overlapping_jobs():
            # TODO: crbug.com/375551
            message += ('HQE %s is using a host in use by another job. This '
                        'could be because of a frontend special task, in which '
                        'case they will only use the host sequentially. ' %
                        offending_job)
        if message:
            email_manager.manager.enqueue_notify_email(subject, message)


    @_timer.decorate
    def tick(self):
        logging.info('Calling new tick.')
        logging.info('Leasing hosts for frontend tasks.')
        self._lease_hosts_of_frontend_tasks()
        logging.info('Finding hosts for new jobs.')
        self._schedule_jobs()
        logging.info('Releasing unused hosts.')
        self._release_hosts()
        logging.info('Checking host assignments.')
        self._check_host_assignments()
        logging.info('Calling email_manager.')
        email_manager.manager.send_queued_emails()


class DummyHostScheduler(BaseHostScheduler):
    """A dummy host scheduler that doesn't acquire or release hosts."""

    def __init__(self):
        pass


    def tick(self):
        pass


def handle_signal(signum, frame):
    """Sigint handler so we don't crash mid-tick."""
    global _shutdown
    _shutdown = True
    logging.info("Shutdown request received.")


def initialize(testing=False):
    """Initialize the host scheduler."""
    if testing:
        # Don't import testing utilities unless we're in testing mode,
        # as the database imports have side effects.
        from autotest_lib.scheduler import rdb_testing_utils
        rdb_testing_utils.FileDatabaseHelper().initialize_database_for_testing(
                db_file_path=rdb_testing_utils.FileDatabaseHelper.DB_FILE)
    global _db_manager
    _db_manager = scheduler_lib.ConnectionManager()
    scheduler_lib.setup_logging(
            os.environ.get('AUTOTEST_SCHEDULER_LOG_DIR', None),
            None, timestamped_logfile_prefix='host_scheduler')
    logging.info("Setting signal handler")
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    scheduler_models.initialize()


def parse_arguments(argv):
    """
    Parse command line arguments

    @param argv: argument list to parse
    @returns:    parsed arguments.
    """
    parser = argparse.ArgumentParser(description='Host scheduler.')
    parser.add_argument('--testing', action='store_true', default=False,
                        help='Start the host scheduler in testing mode.')
    return parser.parse_args(argv)


def main():
    if _monitor_db_host_acquisition:
        logging.info('Please set inline_host_acquisition=False in the shadow '
                     'config before starting the host scheduler.')
        # The upstart job for the host scheduler understands exit(0) to mean
        # 'don't respawn'. This is desirable when the job scheduler is acquiring
        # hosts inline.
        sys.exit(0)
    try:
        initialize(parse_arguments(sys.argv[1:]).testing)
        host_scheduler = HostScheduler()
        while not _shutdown:
            host_scheduler.tick()
            time.sleep(_tick_pause_sec)
    except Exception:
        email_manager.manager.log_stacktrace(
                'Uncaught exception; terminating host_scheduler.')
        raise
    finally:
        email_manager.manager.send_queued_emails()
        _db_manager.disconnect()


if __name__ == '__main__':
    main()
