# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This file contains utility functions for host_history.

import collections

import common
from autotest_lib.client.common_lib import time_utils
from autotest_lib.client.common_lib.cros.graphite import es_utils
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.afe import models


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
        t_curr = entry['fields']['time_recorded'][0]

        #If it is locked, then we put into locked_intervals
        if state_prev:
            locked_intervals.append((t_prev, t_curr))

        # update vars
        t_prev = t_curr
        state_prev = entry['fields']['locked'][0]
    if state_prev:
        locked_intervals.append((t_prev, t_end))
    return locked_intervals


def find_most_recent_entry_before(t, type_str, hostname, fields, index):
    """Returns the fields of the most recent entry before t.

    @param t: time we are interested in.
    @param type_str: _type in esdb, such as 'host_history' (string)
    @param hostname: hostname of DUT (string)
    @param fields: list of fields we are interested in
    @param index: index in elasticsearch to query data for.
    @returns: time, field_value of the latest entry.
    """
    query = es_utils.create_range_eq_query_multiple(
            fields_returned=fields,
            equality_constraints=[('_type', type_str),
                                  ('hostname', hostname)],
            range_constraints=[('time_recorded', None, t)],
            size=1,
            sort_specs=[{'time_recorded': 'desc'}])
    result = es_utils.execute_query(
            query, index,
            es_utils.METADATA_ES_SERVER, es_utils.ES_PORT)
    if result['hits']['total'] > 0:
        # If fields are not specified, the query returns all data for the
        # record under key "_source"
        key = 'fields' if fields else '_source'
        return es_utils.convert_hit(result['hits']['hits'][0][key])
    return {}


def host_history_intervals(t_start, t_end, hostname, size, index):
    """Gets stats for a host.

    @param t_start: beginning of time period we are interested in.
    @param t_end: end of time period we are interested in.
    @param hostname: hostname for the host we are interested in (string)
    @param size: maximum number of entries returned per query
    @param index: index in elasticsearch to query data for.
    @returns: dictionary, num_entries_found
        dictionary of status: time spent in that status
        num_entries_found: number of host history entries
                           found in [t_start, t_end]

    """
    lock_history_recent = find_most_recent_entry_before(
            t=t_start, type_str='lock_history', hostname=hostname,
            fields=['time_recorded', 'locked'], index=index)
    # I use [0] and [None] because lock_history_recent's type is list.
    t_lock = lock_history_recent.get('time_recorded', None)
    t_lock_val = lock_history_recent.get('locked', None)
    host_history_recent = find_most_recent_entry_before(
            t=t_start, type_str='host_history', hostname=hostname,
            fields=None, index=index)
    t_host = host_history_recent.get('time_recorded', None)
    t_host_stat = host_history_recent.get('status', None)
    t_metadata = es_utils.get_metadata(host_history_recent,
                                       ['time_recorded', 'status'])

    status_first = t_host_stat if t_host else 'Ready'
    t = min([t for t in [t_lock, t_host, t_start] if t])

    query_lock_history = es_utils.create_range_eq_query_multiple(
            fields_returned=['locked', 'time_recorded'],
            equality_constraints=[('_type', 'lock_history'),
                                  ('hostname', hostname)],
            range_constraints=[('time_recorded', t, t_end)],
            size=size,
            sort_specs=[{'time_recorded': 'asc'}])

    lock_history_entries = es_utils.execute_query(
            query_lock_history, index,
            es_utils.METADATA_ES_SERVER, es_utils.ES_PORT)

    locked_intervals = lock_history_to_intervals(t_lock_val, t, t_end,
                                                 lock_history_entries)
    query_host_history = es_utils.create_range_eq_query_multiple(
            fields_returned=None,
            equality_constraints=[("_type", "host_history"),
                                  ("hostname", hostname)],
            range_constraints=[("time_recorded", t_start, t_end)],
            size=size,
            sort_specs=[{"time_recorded": "asc"}])
    host_history_entries = es_utils.execute_query(
            query_host_history, index,
            es_utils.METADATA_ES_SERVER, es_utils.ES_PORT)
    num_entries_found = host_history_entries['hits']['total']
    t_prev = t_start
    status_prev = status_first
    metadata_prev = t_metadata
    intervals_of_statuses = collections.OrderedDict()

    for entry in host_history_entries['hits']['hits']:
        t_curr = entry['_source']['time_recorded']
        status_curr = entry['_source']['status']
        metadata = es_utils.get_metadata(entry['_source'],
                                         ['time_recorded', 'status'])
        intervals_of_statuses.update(calculate_status_times(
                t_prev, t_curr, status_prev, metadata_prev, locked_intervals))
        # Update vars
        t_prev = t_curr
        status_prev = status_curr
        metadata_prev = metadata

    # Do final as well.
    intervals_of_statuses.update(calculate_status_times(
            t_prev, t_end, status_prev, metadata_prev, locked_intervals))
    return intervals_of_statuses, num_entries_found


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


def aggregate_multiple_hosts(intervals_of_statuses_list):
    """Aggregates history of multiple hosts

    @param intervals_of_statuses_list: A list of dictionaries where keys
        are tuple (ti, tf), and value is the status along with other metadata.
    @returns: A dictionary where keys are strings, e.g. 'status' and
              value is total time spent in that status among all hosts.
    """
    stats_all = prepopulate_dict(models.Host.Status.names, 0.0,
                                 extras=['Locked'])
    num_hosts = len(intervals_of_statuses_list)
    for intervals_of_statuses in intervals_of_statuses_list:
        total_times = calculate_total_times(intervals_of_statuses)
        for status, delta in total_times.iteritems():
            stats_all[status] += delta
    return stats_all, num_hosts


def get_stats_string_aggregate(labels, t_start, t_end, aggregated_stats,
                               num_hosts):
    """Returns string reporting overall host history for a group of hosts.

    @param labels: A list of labels useful for describing the group
                   of hosts these overall stats represent.
    @param t_start: beginning of time period we are interested in.
    @param t_end: end of time period we are interested in.
    @param aggregated_stats: A dictionary where keys are string, e.g. 'status'
        value is total time spent in that status among all hosts.
    @returns: string representing the aggregate stats report.
    """
    result = 'Overall stats for hosts: %s \n' % (', '.join(labels))
    result += ' %s - %s \n' % (time_utils.epoch_time_to_date_string(t_start),
                               time_utils.epoch_time_to_date_string(t_end))
    result += ' Number of total hosts: %s \n' % (num_hosts)
    # This is multiplied by time_spent to get percentage_spent
    multiplication_factor = 100.0 / ((t_end - t_start) * num_hosts)
    for status, time_spent in aggregated_stats.iteritems():
        # Normalize by the total time we are interested in among ALL hosts.
        spaces = ' ' * (15 - len(status))
        percent_spent = multiplication_factor * time_spent
        result += '    %s: %s %.2f %%\n' % (status, spaces, percent_spent)
    result += '- -- --- ---- ----- ---- --- -- -\n'
    return result


def get_overall_report(label, t_start, t_end, intervals_of_statuses_list):
    """Returns string reporting overall host history for a group of hosts.

    @param label: A string that can be useful for showing what type group
        of hosts these overall stats represent.
    @param t_start: beginning of time period we are interested in.
    @param t_end: end of time period we are interested in.
    @param intervals_of_statuses_list: A list of dictionaries where keys
        are tuple (ti, tf), and value is the status along with other metadata,
        e.g., task_id, task_name, job_id etc.
    """
    stats_all, num_hosts = aggregate_multiple_hosts(
            intervals_of_statuses_list)
    return get_stats_string_aggregate(
            label, t_start, t_end, stats_all,num_hosts)


def get_report_for_host(t_start, t_end, hostname, size,
                        print_each_interval, index):
    """Gets stats report for a host

    @param t_start: beginning of time period we are interested in.
    @param t_end: end of time period we are interested in.
    @param hostname: hostname for the host we are interested in (string)
    @param print_each_interval: True or False, whether we want to
                                display all intervals
    @param index: index in elasticsearch to query data for.
    @returns: stats report for this particular host (string)
    """
    intervals_of_statuses, num_entries_found = host_history_intervals(
            t_start, t_end, hostname, size, index)
    total_times = calculate_total_times(intervals_of_statuses)
    return (get_stats_string(
                    t_start, t_end, total_times, intervals_of_statuses,
                    hostname, num_entries_found, print_each_interval),
                    intervals_of_statuses)


def get_stats_string(t_start, t_end, total_times, intervals_of_statuses,
                     hostname, num_entries_found, print_each_interval):
    """Returns string reporting host_history for this host.
    @param t_start: beginning of time period we are interested in.
    @param t_end: end of time period we are interested in.
    @param total_times: dictionary where key=status,
                        value=(time spent in that status)
    @param intervals_of_statuses: dictionary where keys is tuple (ti, tf),
              and value is the status along with other metadata.
    @param hostname: hostname for the host we are interested in (string)
    @param num_entries_found: Number of entries found for the host in es
    @param print_each_interval: boolean, whether to print each interval
    """
    delta = t_end - t_start
    result = 'usage stats for host: %s \n' % (hostname)
    result += ' %s - %s \n' % (time_utils.epoch_time_to_date_string(t_start),
                               time_utils.epoch_time_to_date_string(t_end))
    result += ' Num entries found in this interval: %s\n' % (num_entries_found)
    for status, value in total_times.iteritems():
        spaces = (15 - len(status)) * ' '
        result += '    %s: %s %.2f %%\n' % (status, spaces, 100*value/delta)
    result += '- -- --- ---- ----- ---- --- -- -\n'
    if print_each_interval:
        for interval, status_info in intervals_of_statuses.iteritems():
            t0, t1 = interval
            t0_string = time_utils.epoch_time_to_date_string(t0)
            t1_string = time_utils.epoch_time_to_date_string(t1)
            status = status_info['status']
            spaces = (15 - len(status)) * ' '
            delta = int(t1-t0)
            result += '    %s  :  %s %s %s %ss\n' % (t0_string, t1_string,
                                                    status_info['status'],
                                                    spaces,
                                                    delta,
                                                    )
    return result


def calculate_status_times(t_start, t_end, int_status, metadata,
                           locked_intervals):
    """Returns a list of intervals along w/ statuses associated with them.

    @param t_start: start time
    @param t_end: end time
    @param int_status: status of [t_start, t_end] if not locked
    @param metadata: metadata of the status change, e.g., task_id, task_name.
    @param locked_intervals: list of tuples denoting intervals of locked states
    @returns: dictionary where key = (t_interval_start, t_interval_end),
                               val = (status, metadata)
              t_interval_start: beginning of interval for that status
              t_interval_end: end of the interval for that status
              status: string such as 'Repair Failed', 'Locked', etc.
              metadata: A dictionary of metadata, e.g.,
                              {'task_id':123, 'task_name':'Reset'}
    """
    statuses = collections.OrderedDict()

    prev_interval_end = t_start

    # TODO: Put allow more information here in info/locked status
    status_info = {'status': int_status,
                   'metadata': metadata}
    locked_info = {'status': 'Locked',
                   'metadata': {}}
    if not locked_intervals:
        statuses[(t_start, t_end)] = status_info
        return statuses
    for lock_start, lock_end in locked_intervals:
        if lock_start > t_end:
            # optimization to break early
            # case 0
            # Timeline of status change: t_start t_end
            # Timeline of lock action:                   lock_start lock_end
            break
        elif lock_end < t_start:
            # case 1
            #                      t_start    t_end
            # lock_start lock_end
            continue
        elif lock_end < t_end and lock_start > t_start:
            # case 2
            # t_start                       t_end
            #          lock_start lock_end
            statuses[(prev_interval_end, lock_start)] = status_info
            statuses[(lock_start, lock_end)] = locked_info
        elif lock_end > t_start and lock_start < t_start:
            # case 3
            #             t_start          t_end
            # lock_start          lock_end
            statuses[(t_start, lock_end)] = locked_info
        elif lock_start < t_end and lock_end > t_end:
            # case 4
            # t_start             t_end
            #          lock_start        lock_end
            statuses[(prev_interval_end, lock_start)] = status_info
            statuses[(lock_start, t_end)] = locked_info
        prev_interval_end = lock_end
        # Otherwise we are in the case where lock_end < t_start OR
        # lock_start > t_end, which means the lock doesn't apply.
    if t_end > prev_interval_end:
        # This is to avoid logging the same time
        statuses[(prev_interval_end, t_end)] = status_info
    return statuses
