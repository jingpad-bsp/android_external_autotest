# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This file contains utility functions for host_history.

import collections
import datetime

import common
from autotest_lib.client.common_lib.cros.graphite import es_utils
from autotest_lib.client.common_lib.cros.graphite import es_test_utils
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.afe import models


def unix_time_to_readable_date(unix_time):
    """ Converts unix time (float) to a human readable date string.

    @param unix_time: Float of the current time since epoch time.
    @returns: string formatted in the following way:
        "yyyy-mm-dd hh-mm-ss"
    """
    if unix_time:
        return datetime.datetime.fromtimestamp(
                int(unix_time)).strftime('%Y-%m-%d %H:%M:%S')
    return None


def prepopulate_dict(keys, value, extras=None):
    """Creates a dictionary with val=value for each key.

    @param keys: list of keys
    @param value: the value of each entry in the dict.
    @param extras: list of additional keys
    @returns: dictionary
    """
    result = collections.OrderedDict()
    extra_keys = tuple(extras if extras else [])
    for key in keys + extra_keys:
        result[key] = value
    return result


def lock_history_to_intervals(initial_lock_val, t_start, t_end, lock_history):
    """Converts lock history into a list of intervals of locked times.

    @param initial_lock_val: Initial value of the lock (False or True)
    @param t_start: beginning of the time period we are interested in.
    @param t_end: end of the time period we are interested in.
    @param lock_history: Result of querying es for locks (dict)
           This dictionary should contain keys 'locked' and 'time_recorded'
    @returns: Returns a list of tuples where the elements of each tuples
           represent beginning and end of intervals of locked, respectively.
    """
    locked_intervals = []
    t_prev = t_start
    state_prev = initial_lock_val
    for entry in lock_history['hits']['hits']:
        t_curr = entry['fields']['time_recorded']

        #If it is locked, then we put into locked_intervals
        if state_prev:
            locked_intervals.append((t_prev, t_curr))

        # update vars
        t_prev = t_curr
        state_prev = entry['fields']['status']
    if state_prev:
        locked_intervals.append((t_prev, t_end))
    return locked_intervals


def find_most_recent_entry_before(t, type_str, hostname, fields):
    """Returns the fields of the most recent entry before t.

    @param t: time we are interested in.
    @param type_str: _type in esdb, such as 'host_history' (string)
    @param hostname: hostname of DUT (string)
    @param fields: list of fields we are interested in
    @returns: time, field_value of the latest entry.
    """
    # TODO(michaelliang): Rename migrate all non test-only
    #   functions in es_test_utils.py to es_utils.py
    query = es_test_utils.create_range_eq_query_multiple(
            fields_returned=fields,
            equality_constraints=[('_type', type_str),
                                  ('hostname', hostname)],
            range_constraints=[('time_recorded', None, t)],
            size=1,
            sort_specs=[{'time_recorded': 'desc'}])
    result = es_test_utils.execute_query(
            query, es_utils.INDEX_METADATA,
            es_utils.METADATA_ES_SERVER, es_utils.ES_PORT)
    if result['hits']['total'] > 0:
        res_fields = result['hits']['hits'][0]['fields']
        return res_fields
    return {}


def host_history_intervals(t_start, t_end, hostname, size):
    """Gets stats for a host.

    @param t_start: beginning of time period we are interested in.
    @param t_end: end of time period we are interested in.
    @param hostname: hostname for the host we are interested in (string)
    @param size: maximum number of entries returned per query
    @returns: dictionary, num_entries_found
        dictionary of status: time spent in that status
        num_entries_found: number of host history entries
                           found in [t_start, t_end]

    """
    lock_history_recent = find_most_recent_entry_before(
            t=t_start, type_str='lock_history', hostname=hostname,
            fields=['time_recorded', 'locked'])
    # I use [0] and [None] because lock_history_recent's type is list.
    t_lock = lock_history_recent.get('time_recorded', [None])[0]
    t_lock_val = lock_history_recent.get('locked', [None])[0]
    host_history_recent = find_most_recent_entry_before(
            t=t_start, type_str='host_history', hostname=hostname,
            fields=['time_recorded', 'status', 'dbg_str'])
    t_host = host_history_recent.get('time_recorded', [None])[0]
    t_host_stat = host_history_recent.get('status', [None])[0]
    t_dbg_str = host_history_recent.get('dbg_str', [''])[0]

    status_first = t_host_stat if t_host else 'Ready'
    t = min([t for t in [t_lock, t_host, t_start] if t])

    query_lock_history = es_test_utils.create_range_eq_query_multiple(
            fields_returned=['locked', 'time_recorded'],
            equality_constraints=[('_type', 'lock_history'),
                                  ('hostname', hostname)],
            range_constraints=[('time_recorded', t, t_end)],
            size=size,
            sort_specs=[{'time_recorded': 'asc'}])

    lock_history_entries = es_test_utils.execute_query(
            query_lock_history, es_utils.INDEX_METADATA,
            es_utils.METADATA_ES_SERVER, es_utils.ES_PORT)

    locked_intervals = lock_history_to_intervals(t_lock_val, t, t_end,
                                                 lock_history_entries)
    query_host_history = es_test_utils.create_range_eq_query_multiple(
            fields_returned=["hostname", "time_recorded", "dbg_str", "status"],
            equality_constraints=[("_type", "host_history"),
                                  ("hostname", hostname)],
            range_constraints=[("time_recorded", t_start, t_end)],
            size=size,
            sort_specs=[{"time_recorded": "asc"}])
    host_history_entries = es_test_utils.execute_query(
            query_host_history, es_utils.INDEX_METADATA,
            es_utils.METADATA_ES_SERVER, es_utils.ES_PORT)
    num_entries_found = host_history_entries['hits']['total']
    t_prev = t_start
    status_prev = status_first
    dbg_prev = t_dbg_str
    intervals_of_statuses = collections.OrderedDict()

    for entry in host_history_entries['hits']['hits']:
        t_curr = entry['fields']['time_recorded'][0]
        status_curr = entry['fields']['status'][0]
        dbg_str = entry['fields']['dbg_str'][0]
        intervals_of_statuses.update(calculate_all_status_times(
                t_prev, t_curr, status_prev, dbg_prev, locked_intervals))
        # Update vars
        t_prev = t_curr
        status_prev = status_curr
        dbg_prev = dbg_str

    # Do final as well.
    intervals_of_statuses.update(calculate_all_status_times(
            t_prev, t_end, status_prev, dbg_prev, locked_intervals))
    return intervals_of_statuses, num_entries_found


def host_history_stats_report(t_start, t_end, hostname, size,
                              print_each_interval):
    """Gets stats report for a host

    @param t_start: beginning of time period we are interested in.
    @param t_end: end of time period we are interested in.
    @param hostname: hostname for the host we are interested in (string)
    @param print_each_interval: True or False, whether we want to
                                display all intervals
    @returns: stats report for this particular host (string)
    """
    intervals_of_statuses, num_entries_found = host_history_intervals(
            t_start, t_end, hostname, size)
    total_times = calculate_total_times(intervals_of_statuses)
    return get_stats_string(t_start, t_end, total_times, intervals_of_statuses,
                        hostname, num_entries_found, print_each_interval)


def calculate_total_times(intervals_of_statuses):
    """Calculates total times in each status.

    @param intervals_of_statuses: ordereddict where key=(ti, tf) and val=status
    @returns: dictionary where key=status value=time spent in that status
    """
    total_times = prepopulate_dict(models.Host.Status.names, 0.0,
                                   extras=['Locked'])
    for key, status_info in intervals_of_statuses.iteritems():
        ti, tf = key
        total_times[status_info['status']] += tf - ti
    return total_times


def get_stats_string(t_start, t_end, total_times, intervals_of_statuses,
                     hostname, num_entries_found, print_each_interval):
    """Returns string reporting host_history for this host.
    @param t_start: beginning of time period we are interested in.
    @param t_end: end of time period we are interested in.
    @param total_times: dictionary where key=status,
                        value=(time spent in that status)
    @param intervals_of_statuses: dictionary where keys is tuple (ti, tf),
              and value is the status along with debug string (if applicable)
              Note: dbg_str is '' if status is locked.
    @param hostname: hostname for the host we are interested in (string)
    @param num_entries_found: Number of entries found for the host in es
    @param print_each_interval: boolean, whether to print each interval
    """
    delta = t_end - t_start
    result = 'usage stats for host: %s \n' % (hostname)
    result += ' %s - %s \n' % (unix_time_to_readable_date(t_start),
                               unix_time_to_readable_date(t_end))
    result += ' Num entries found in this interval: %s\n' % (num_entries_found)
    for status, value in total_times.iteritems():
        spaces = (15 - len(status)) * ' '
        result += '    %s: %s %.2f %%\n' % (status, spaces, 100*value/delta)
    result += '- -- --- ---- ----- ---- --- -- -\n'
    if print_each_interval:
        for interval, status_info in intervals_of_statuses.iteritems():
            t0, t1 = interval
            t0_string = unix_time_to_readable_date(t0)
            t1_string = unix_time_to_readable_date(t1)
            status = status_info['status']
            spaces = (15 - len(status)) * ' '
            delta = int(t1-t0)
            result += '    %s  :  %s %s %s %ss\n' % (t0_string, t1_string,
                                                    status_info['status'],
                                                    spaces,
                                                    delta,
                                                    )
    return result


def calculate_all_status_times(ti, tf, int_status, dbg_str, locked_intervals):
    """Returns a list of intervals along w/ statuses associated with them.

    @param ti: start time
    @param tf: end time
    @param int_status: status of [ti, tf] if not locked
    @param dbg_str: dbg_str to pass in
    @param locked_intervals: list of utples denoting intervals of locked states
    @returns: dictionary where key = (t_interval_start, t_interval_end),
                               val = (status, dbg_str)
              t_interval_start: beginning of interval for that status
              t_interval_end: end of the interval for that status
              status: string such as 'Repair Failed', 'Locked', etc.
              dbg_str: '' if status is 'Locked', otherwise it will
                       be something like: (String)
                       Task: Special Task 18858263 (host 172.22.169.106,
                                                    task Repair,
                                                    time 2014-07-27 20:01:15)
    """
    statuses = collections.OrderedDict()

    prev_interval_end = ti

    # TODO: Put allow more information here in info/locked status
    status_info = {'status': int_status,
                   'dbg_str': dbg_str}
    locked_info = {'status': 'Locked',
                   'dbg_str': ''}
    if not locked_intervals:
        statuses[(ti, tf)] = status_info
        return statuses
    for lock_start, lock_end in locked_intervals:
        if lock_start > tf:
            # optimization to break early
            # case 0
            # ti    tf
            #           ls le
            break
        elif lock_end < ti:
            # case 1
            #       ti    tf
            # ls le
            continue
        elif lock_end < tf and lock_start > ti:
            # case 2
            # ti         tf
            #    ls   le
            statuses[(prev_interval_end, lock_start)] = status_info
            statuses[(lock_start, lock_end)] = locked_info
        elif lock_end > ti and lock_start < ti:
            # case 3
            #   ti         tf
            # ls   le
            statuses[(ti, lock_end)] = locked_info
        elif lock_start < tf and lock_end > tf:
            # case 4
            # ti        tf
            #       ls      le
            statuses[(prev_interval_end, lock_start)] = status_info
            statuses[(lock_start, tf)] = locked_info
        prev_interval_end = lock_end
        # Otherwise we are in the case where lock_end < ti OR lock_start > tf,
        #  which means the lock doesn't apply.
    if tf > prev_interval_end:
        # This is to avoid logging the same time
        statuses[(prev_interval_end, tf)] = status_info
    return statuses
