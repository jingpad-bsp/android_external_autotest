# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime, time
from autotest_lib.client.common_lib import base_job


TIME_FMT = '%Y-%m-%d %H:%M:%S'


def _collate_aborted(current_value, entry):
    """
    reduce() over a list of HostQueueEntries for a job; True if any aborted.

    Functor that can be reduced()ed over a list of
    HostQueueEntries for a job.  If any were aborted
    (|entry.aborted| exists and is True), then the reduce() will
    return True.

    Ex:
      entries = AFE.run('get_host_queue_entries', job=job.id)
      reduce(_collate_aborted, entries, False)

    @param current_value: the current accumulator (a boolean).
    @param entry: the current entry under consideration.
    @return the value of |entry.aborted| if it exists, False if not.
    """
    return current_value or ('aborted' in entry and entry['aborted'])


def _status_is_relevant(status):
    """
    Indicates whether the status of a given test is meaningful or not.

    @param status: frontend.TestStatus object to look at.
    @return True if this is a test result worth looking at further.
    """
    return not (status.test_name.startswith('SERVER_JOB') or
                status.test_name.startswith('CLIENT_JOB'))


def wait_for_results(afe, tko, jobs):
    """
    Wait for results of all tests in all jobs in |jobs|.

    Currently polls for results every 5s.  When all results are available,
    @return a list of Statuses, one per test: (status, subdir, name, reason)
    """
    while jobs:
        for job in list(jobs):
            if not afe.get_jobs(id=job.id, finished=True):
                continue

            jobs.remove(job)

            entries = afe.run('get_host_queue_entries', job=job.id)
            if reduce(_collate_aborted, entries, False):
                yield Status('ABORT', job.name)
            else:
                statuses = tko.get_status_counts(job=job.id)
                for s in filter(_status_is_relevant, statuses):
                    yield Status(s.status, s.test_name, s.reason,
                                 s.test_started_time,
                                 s.test_finished_time)
        time.sleep(5)


class Status(object):
    """
    A class representing a test result.

    Stores all pertinent info about a test result and, given a callable
    to use, can record start, result, and end info appropriately.

    @var _status: status code, e.g. 'INFO', 'FAIL', etc.
    @var _test_name: the name of the test whose result this is.
    @var _reason: message explaining failure, if any.
    @var _begin_timestamp: when test started (int, in seconds since the epoch).
    @var _end_timestamp: when test finished (int, in seconds since the epoch).

    @var TIME_FMT: format string for parsing human-friendly timestamps.
    """
    _status = None
    _test_name = None
    _reason = None
    _begin_timestamp = None
    _end_timestamp = None


    def __init__(self, status, test_name, reason='', begin_time_str=None,
                 end_time_str=None):
        """
        Constructor

        @param status: status code, e.g. 'INFO', 'FAIL', etc.
        @param test_name: the name of the test whose result this is.
        @param reason: message explaining failure, if any; Optional.
        @param begin_time_str: when test started (in TIME_FMT); now() if None.
        @param end_time_str: when test finished (in TIME_FMT); now() if None.
        """

        self._status = status
        self._test_name = test_name
        self._reason = reason
        if begin_time_str:
            self._begin_timestamp = int(time.mktime(
                datetime.datetime.strptime(
                    begin_time_str, TIME_FMT).timetuple()))
        else:
            self._begin_timestamp = int(time.time())

        if end_time_str:
            self._end_timestamp = int(time.mktime(
                datetime.datetime.strptime(
                    end_time_str, TIME_FMT).timetuple()))
        else:
            self._end_timestamp = int(time.time())


    def record_start(self, record_entry):
        """
        Use record_entry to log message about start of test.

        @param record_entry: a callable to use for logging.
               prototype:
                   record_entry(base_job.status_log_entry)
        """
        record_entry(
            base_job.status_log_entry(
                'START', None, self._test_name, '',
                None, self._begin_timestamp))


    def record_result(self, record_entry):
        """
        Use record_entry to log message about result of test.

        @param record_entry: a callable to use for logging.
               prototype:
                   record_entry(base_job.status_log_entry)
        """
        record_entry(
            base_job.status_log_entry(
                self._status, None, self._test_name, self._reason,
                None, self._end_timestamp))


    def record_end(self, record_entry):
        """
        Use record_entry to log message about end of test.

        @param record_entry: a callable to use for logging.
               prototype:
                   record_entry(base_job.status_log_entry)
        """
        record_entry(
            base_job.status_log_entry(
                'END %s' % self._status, None, self._test_name, '',
                None, self._end_timestamp))
