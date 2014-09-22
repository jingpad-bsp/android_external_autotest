#!/usr/bin/env python
# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import sys
import time

import common
from autotest_lib.frontend import setup_django_environment

from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib import time_utils
from autotest_lib.frontend.afe import models as afe_models


# Status values that can be returned by HostJobHistory.last_status()
_NO_STATUS = 0
_UNKNOWN = 1
_WORKING = 2
_BROKEN = 3

# List of string values to display for the status values above,
# indexed by those values.
_STATUS_IDS = ['--', 'XX', 'OK', 'NO']


# Default time interval for the --duration option when a value isn't
# specified on the command line.
_DEFAULT_DURATION = 12


def _parse_time(time_string):
    return int(time_utils.date_string_to_epoch_time(time_string))


class JobAdapter(object):
    """Adapter class for special tasks and test jobs.

    This adapter provides a standard interface wrapper around the
    database model objects describing activity on a DUT.  This is an
    abstract superclass, with concrete subclasses for HostQueueEntry
    and SpecialTask objects.

    @property start_time  Time the job or task began execution.
    @property end_time    Time the job or task finished execution.

    """

    get_config_value = global_config.global_config.get_config_value
    _AFE_HOSTNAME = get_config_value('SERVER', 'hostname')
    _LOG_URL_PATTERN = get_config_value('CROS', 'log_url_pattern')

    @classmethod
    def get_log_url(cls, logdir):
        """Return a URL to job results.

        The URL is constructed from a base URL determined by the
        global config, plus the relative path of the job's log
        directory.

        @param logdir Relative path of the results log directory.

        @return A URL to the requested results log.

        """
        return cls._LOG_URL_PATTERN % (cls._AFE_HOSTNAME, logdir)


    def __init__(self, start_time, end_time):
        self.start_time = int(time.mktime(start_time.timetuple()))
        if end_time:
            self.end_time = int(time.mktime(end_time.timetuple()))
        else:
            self.end_time = None


    def __cmp__(self, other):
        """Compare two jobs by their start time.

        This is a standard Python `__cmp__` method to allow sorting
        `JobAdapter` objects by when they ran on the DUT.

        @param other The `JobAdapter` object to compare to `self`.

        """
        return self.start_time - other.start_time


    @property
    def task_type(self):
        """Return a letter indicating the type of task this is.

        The letter indicates the type of task as follows:
          'P' - A provision job.
          'R' - A repair job.
          'S' - A reset job.
          'T' - Any regular test job.
          'V' - A verify job.

        @return A letter indicating the type of job.

        """
        raise NotImplemented()


    @property
    def job_url(self):
        """Return the URL for this job's results."""
        raise NotImplemented()


    @property
    def dut_status(self):
        """Return the status of the DUT after this job completed.

        The status is derived depending on the type of the job, and
        the job's outcome.  One of the following values is returned:
          _UNKNOWN - It's not known whether the DUT was working or
              not when the job completed.
          _WORKING - The DUT appeared to be working when the job
              completed.
          _BROKEN - The DUT appeared not to be working when the job
              completed.

        @return A valid status value.

        """
        raise NotImplemented()


class SpecialTaskJobAdapter(JobAdapter):
    """JobAdapter for special tasks.

    This class wraps the standard JobAdapter interface around a row
    in the `afe_special_tasks` table.

    """

    @classmethod
    def get_tasks(cls, host_id, start_time, end_time):
        """Return special tasks for a host in a given time range.

        Return a list of `SpecialTaskJobAdapter` objects
        representing all special task that ran on the given host in
        the given time range.  The list is ordered as it was
        returned by the database.

        @param host_id     Database host id of the desired host.
        @param start_time  Start time of the range of interest.
        @param end_time    End time of the range of interest.

        @return A list of `SpecialTaskJobAdapter` objects.

        """
        filter_start = time_utils.epoch_time_to_date_string(start_time)
        filter_end = time_utils.epoch_time_to_date_string(end_time)
        tasks = afe_models.SpecialTask.objects.filter(
                host_id=host_id,
                time_started__gte=filter_start,
                time_started__lte=filter_end,
                is_complete=True)
        return [cls(t) for t in tasks]


    def __init__(self, afetask):
        self._afetask = afetask
        super(SpecialTaskJobAdapter, self).__init__(
                afetask.time_started, afetask.time_finished)


    @property
    def task_type(self):
        if self._afetask.task == 'Reset':
            return 'S'
        return self._afetask.task[0]


    @property
    def job_url(self):
        logdir = ('hosts/%s/%s-%s' %
                  (self._afetask.host.hostname, self._afetask.id,
                   self._afetask.task.lower()))
        return SpecialTaskJobAdapter.get_log_url(logdir)


    @property
    def dut_status(self):
        if self._afetask.success:
            return _WORKING
        elif self._afetask.task == 'Repair':
            return _BROKEN
        else:
            return _UNKNOWN


class TestJobAdapter(JobAdapter):
    """JobAdapter for regular test jobs.

    This class wraps the standard JobAdapter interface around a row
    in the `afe_host_queue_entries` table.

    """

    @classmethod
    def get_hqes(cls, host_id, start_time, end_time):
        """Return HQEs for a host in a given time range.

        Return a list of `TestJobAdapter` objects representing all
        the HQEs of all the jobs that ran on the given host in the
        given time range.  The list is ordered as it was returned
        by the database.

        @param host_id     Database host id of the desired host.
        @param start_time  Start time of the range of interest.
        @param end_time    End time of the range of interest.

        @return A list of `TestJobAdapter` objects.

        """
        filter_start = time_utils.epoch_time_to_date_string(start_time)
        filter_end = time_utils.epoch_time_to_date_string(end_time)
        hqelist = afe_models.HostQueueEntry.objects.filter(
                host_id=host_id,
                started_on__gte=filter_start,
                started_on__lte=filter_end,
                complete=True)
        return [cls(hqe) for hqe in hqelist]


    def __init__(self, hqe):
        self._hqe = hqe
        super(TestJobAdapter, self).__init__(
                hqe.started_on, hqe.finished_on)


    @property
    def task_type(self):
        return 'T'


    @property
    def job_url(self):
        logdir = '%s-%s' % (self._hqe.job.id, self._hqe.job.owner)
        return TestJobAdapter.get_log_url(logdir)


    @property
    def dut_status(self):
        if self._hqe.finished_on is not None:
            return _WORKING
        else:
            return _UNKNOWN


class HostJobHistory(object):
    """Class to query and remember DUT execution history.

    This class is responsible for querying the database to determine
    the history of a single DUT in a time interval of interest, and
    for remembering the query results for reporting.

    @property hostname    Host name of the DUT.
    @property start_time  Start of the requested time interval.
    @property end_time    End of the requested time interval.
    @property host        Database host object for the DUT.
    @property history     A list of jobs and special tasks that
                          ran on the DUT in the requested time
                          interval, ordered in reverse, from latest
                          to earliest.

    """

    def __init__(self, hostname, start_time, end_time):
        self.hostname = hostname
        self.start_time = start_time
        self.end_time = end_time
        self.host = None
        self.history = None
        hostlist = afe_models.Host.objects.filter(hostname=hostname)
        if hostlist:
            assert len(hostlist) == 1
            self.host = hostlist[0]
            self.history = self._get_history(start_time, end_time)


    def __iter__(self):
        return self.history.__iter__()


    def _get_history(self, start_time, end_time):
        newtasks = SpecialTaskJobAdapter.get_tasks(
                self.host.id, start_time, end_time)
        newhqes = TestJobAdapter.get_hqes(
                self.host.id, start_time, end_time)
        newhistory = newtasks + newhqes
        newhistory.sort(reverse=True)
        return newhistory


    def is_valid(self):
        """Return whether the host was found in the database."""
        return self.host is not None


    def last_status(self):
        """Return the status of whether the DUT is working.

        This searches the DUT's job history from most to least
        recent, looking for jobs that indicate whether the DUT
        was working.  Return a tuple of `(status, job)`.

        The `status` entry in the tuple is one of these values:
          * _NO_STATUS - The job history is empty.
          * _UNKNOWN - All jobs in the history returned _UNKNOWN
              status.
          * _WORKING - The DUT was working at last check.
          * _FAILED - The DUT likely requires manual intervention.

        The `job` entry in the tuple is the job that led to the
        status diagnosis.  The job will be `None` if the status
        is `_NO_STATUS` or `_UNKNOWN`.

        @return A tuple with the DUT's status and the job that
                determines the status.

        """
        if not self.history:
            return _NO_STATUS, None
        for job in self:
            status = job.dut_status
            if status != _UNKNOWN:
                return job.dut_status, job
        return _UNKNOWN, None


def _print_simple_status(arguments):
    print '%-28s %-2s  %s' % ('hostname', 'S', 'url')
    for hostname in arguments.hostnames:
        history = HostJobHistory(hostname,
                                 arguments.since, arguments.until)
        if history.is_valid():
            status, job = history.last_status()
            if job is None:
                url = '---'
            else:
                url = job.job_url
            summary = '%-2s  %s' % (_STATUS_IDS[status], url)
        else:
            summary = '# no such host'
        print '%-28s %s' % (history.hostname, summary)


def _print_host_history(arguments):
    for hostname in arguments.hostnames:
        print hostname
        history = HostJobHistory(hostname,
                                 arguments.since, arguments.until)
        for job in history:
            start_time = time_utils.epoch_time_to_date_string(job.start_time)
            print '    %s  %s' % (start_time, job.job_url)


def _validate_command(arguments):
    if (arguments.duration is not None and
            arguments.since is not None and arguments.until is not None):
        print >>sys.stderr, ('Can specify at most two of '
                             '--since, --until, and --duration')
        sys.exit(1)
    if (arguments.until is None and (arguments.since is None or
                                     arguments.duration is None)):
        arguments.until = int(time.time())
    if arguments.since is None:
        if arguments.duration is None:
            arguments.duration = _DEFAULT_DURATION
        arguments.since = (arguments.until -
                           arguments.duration * 60 * 60)
    elif arguments.until is None:
        arguments.until = (arguments.since +
                           arguments.duration * 60 * 60)


def _parse_command(argv):
    parser = argparse.ArgumentParser(
            prog=argv[0],
            description='Display DUT status and execution history',
            epilog='You can specify one or two of --since, --until, '
                   'and --duration, but not all three.\n'
                   'The date/time format is "YYYY-MM-DD HH:MM:SS".')
    parser.add_argument('-s', '--since', type=_parse_time,
                        metavar='DATE/TIME',
                        help='starting time for history display')
    parser.add_argument('-u', '--until', type=_parse_time,
                        metavar='DATE/TIME',
                        help='ending time for history display'
                             ' (default: now)')
    parser.add_argument('-d', '--duration', type=int,
                        metavar='HOURS',
                        help='number of hours of history to display'
                             ' (default: %d)' % _DEFAULT_DURATION)
    parser.add_argument('-f', '--full_history', action='store_true')
    parser.add_argument('hostnames',
                        nargs='*',
                        help='host names of DUTs to display')
    arguments = parser.parse_args(argv[1:])
    _validate_command(arguments)
    return arguments


def main(argv):
    """Standard main() for command line processing.

    @param argv Command line arguments (normally sys.argv).

    """
    arguments = _parse_command(argv)
    if arguments.full_history:
        _print_host_history(arguments)
    else:
        _print_simple_status(arguments)


if __name__ == '__main__':
    main(sys.argv)
