#!/usr/bin/env python
# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import sys
import time

import common

from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib import time_utils
from autotest_lib.client.common_lib.cros.graphite import es_utils


# Values used to describe the diagnosis of a DUT.  These values
# are used to indicate both DUT status after a single state
# transition, and also diagnosis of whether the DUT was working
# at the end of a given time interval.
#
# _NO_STATUS:  Used when there are no state transitions recorded in
#     a given time interval.
# _UNKNOWN:  For an individual transition, indicates that the DUT
#     status is unchanged from the previous transition.  For a time
#     interval, indicates that the DUT's status can't be determined
#     from the transition history.
# _WORKING:  Indicates that the DUT was working normally after the
#     transition, or at the end of the time interval.
# _BROKEN:  Indicates that the DUT needed manual repair after the
#     transition, or at the end of the time interval.
#
_NO_STATUS = 0
_UNKNOWN = 1
_WORKING = 2
_BROKEN = 3

# List of string values to display for the diagnosis values above,
# indexed by those values.
_DIAGNOSIS_IDS = ['??', '--', 'OK', 'NO']


# Default time interval for the --duration option when a value isn't
# specified on the command line.
_DEFAULT_DURATION = 12


def _parse_time(time_string):
    return int(time_utils.date_string_to_epoch_time(time_string))


class StateTransition(object):
    """Information about a state transistion in host history.

    This remembers the relevant data from a host history object
    in the elastic search database.  This include primary data from
    the ES database such as the hostname, the AFE host state of the
    transition, and the time of the transition.  It also includes
    secondary data calculated from the primary data.

    State transitions can be caused by either a regular test job or
    a special task.  The specific kind of transition is determined
    by the `job_id` and `task_id` member fields as follows:
      * `self.job_id is not None and self.task_id is None` -
        This indicates a regular job with id `self.job_id`.
      * `self.job_id is None and self.task_id is not None` -
        This indicates a 'Repair' special task with id
        `self.task_id`, triggered on a failed DUT.
      * `self.job_id is not None and self.task_id is not None` -
        This indicates a special task with id `self.task_id`
        associated with an HQE (such as a 'Provision' job).  The HQE
        job has the id `self.job_id`.
    The `job_id` and `task_id` fields cannot both be `None`.

    Each state transition implies a diagnosis about whether the DUT
    was working at the time, based on the `status` value:
      * 'Ready' - The device was working normally at the time of the
        transition.
      * 'Repair Failed' - The device probably needed manual
        intervention at the time of the transition.
      * All other status values - The device's state is unchanged
        from the previous transition.

    @property hostname    Host name of the DUT.
    @property status      DUT state after the transition; valid
                          values are the same as for
                          `afe_hosts.status`.
    @property timestamp   Time when the scheduler recorded the
                          transition.
    @property job_id      ID in the AFE database for the job that
                          triggered the transition.  `None` if the
                          transition was for a special task without
                          an associated HQE.
    @property task_id     ID in the AFE database for the special
                          task that triggered the transition.
                          `None` if the transition was for a regular
                          job.
    @property job_url     URL to the logs for the job that triggered
                          the transition.
    @property diagnosis   Working status of the DUT, derived from
                          `status`.

    """

    get_config_value = global_config.global_config.get_config_value
    _AFE_HOSTNAME = get_config_value('SERVER', 'hostname')
    _LOG_URL_PATTERN = get_config_value('CROS', 'log_url_pattern')

    @classmethod
    def get_transitions(cls, hostname, start_time, end_time):
        """Get a list of StateTransition objects from ES host history.

        The returned list includes all transitions on the given host
        in the given time interval.

        @param hostname    Host for the transitions in the host
                           history.
        @param start_time  Start of the time interval to search.
        @param end_time    End of the time interval to search.

        """
        equality_constraints = [('_type', 'host_history'),
                                ('hostname', hostname)]
        range_constraints = [('time_recorded', start_time, end_time)]
        query = es_utils.create_range_eq_query_multiple(
                    fields_returned=None,
                    equality_constraints=equality_constraints,
                    range_constraints=range_constraints,
                    size=end_time - start_time,
                    sort_specs=[{'time_recorded': 'desc'}])
        result = es_utils.execute_query(query)
        return [cls(o['_source']) for o in result['hits']['hits']]


    def __init__(self, transition_data):
        self.hostname = transition_data['hostname']
        self.status = transition_data['status']
        self.timestamp = transition_data['time_recorded']
        self.job_id = transition_data.get('job_id')
        self.task_id = transition_data.get('task_id')
        if self.task_id is not None:
            logdir = ('hosts/%s/%s-%s' %
                      (self.hostname, self.task_id,
                       transition_data['task_name'].lower()))
        else:
            logdir = '%s-%s' % (self.job_id, transition_data['owner'])
        self.job_url = StateTransition._LOG_URL_PATTERN % (
                StateTransition._AFE_HOSTNAME, logdir)
        self.diagnosis = _UNKNOWN
        if self.status == 'Repair Failed':
            self.diagnosis = _BROKEN
        elif self.status == 'Ready':
            self.diagnosis = _WORKING


class HostStateHistory(object):
    """Class to query and remember DUT state transition history.

    This class is responsible for querying the elastic search
    database to determine the history of a single DUT in a time
    interval of interest, and for remembering the query results for
    reporting.

    @property hostname    Host name of the DUT.
    @property start_time  Start of the requested time interval.
    @property end_time    End of the requested time interval.
    @property history     A list of state transitions on the DUT
                          during the given time interval, ordered
                          from most to least recent.

    """

    def __init__(self, hostname, start_time, end_time):
        self.hostname = hostname
        self.start_time = start_time
        self.end_time = end_time
        self.history = self._get_history(start_time, end_time)

    def __iter__(self):
        return self.history.__iter__()

    def _get_history(self, start_time, end_time):
        return StateTransition.get_transitions(
                self.hostname, start_time, end_time)

    def last_diagnosis(self):
        """Return the most recent diagnosis for the DUT.

        This searches the DUT's state history from most to least
        recent, looking for transitions that indicate whether the
        DUT was working.  Return a tuple of `(diagnosis, transition)`.

        The `diagnosis` entry in the tuple is one of these values:
          * _NO_STATUS - The state transition history is empty.
          * _UNKNOWN - No state in the history indicated a
              positive diagnosis.
          * _WORKING - At last check, the DUT was working.
          * _BROKEN - At last check, the DUT likely required manual
              intervention.

        The `transition` entry in the tuple is the entry that led to
        the diagnosis.  The transition will be `None` if the value
        is `_NO_STATUS` or `_UNKNOWN`.

        @return A tuple with the DUT's status and the transition that
                determined the diagnosis.

        """
        if not self.history:
            return _NO_STATUS, None
        for transition in self:
            diagnosis = transition.diagnosis
            if diagnosis == _BROKEN or diagnosis == _WORKING:
                return diagnosis, transition
        return _UNKNOWN, None


def _print_simple_status(arguments):
    fmt = '%-28s %-2s  %-19s  %s'
    print fmt % ('hostname', 'S', 'last checked', 'URL')
    for hostname in arguments.hostnames:
        history = HostStateHistory(hostname,
                                   arguments.since, arguments.until)
        status, transition = history.last_diagnosis()
        if transition is not None:
            url = transition.job_url
            datestr = time_utils.epoch_time_to_date_string(
                    transition.timestamp)
        else:
            url = '---'
            datestr = '---'
        print fmt % (history.hostname,
                     _DIAGNOSIS_IDS[status],
                     datestr,
                     url)


def _print_host_transitions(arguments):
    for hostname in arguments.hostnames:
        print hostname
        history = HostStateHistory(hostname,
                                   arguments.since, arguments.until)
        for transition in history:
            start_time = time_utils.epoch_time_to_date_string(
                    transition.timestamp)
            print '    %s  %s %s' % (
                    start_time,
                    _DIAGNOSIS_IDS[transition.diagnosis],
                    transition.job_url)


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
        _print_host_transitions(arguments)
    else:
        _print_simple_status(arguments)


if __name__ == '__main__':
    main(sys.argv)
