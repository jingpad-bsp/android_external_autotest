#!/usr/bin/env python

# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This file defines script for getting host_history for DUTs in Autotest.

"""Script for checking host history for a selected group of hosts.

Currently only supports aggregating stats for each host.

Example usage:
    python host_history.py --server=cautotest -n 10000 -l 24 --board=daisy

Output:

    trying to get all duts...
    making the query...
    found all duts. Time to get host_history.
    usage stats for host: chromeos2-row5-rack1-host6
        2014-07-24 10:24:07 - 2014-07-25 10:24:07
            Verifying:        0.00 %
            Running:          0.00 %
            Ready:            100.00 %
            Repairing:        0.00 %
            Repair Failed:    0.00 %
            Cleaning:         0.00 %
            Pending:          0.00 %
            Resetting:        0.00 %
            Provisioning:     0.00 %
            Locked:           0.00 %
    - -- --- ---- ----- ---- --- -- -

Example usage2: more than one host:
    python host_history.py --server=cautotest    -n 1000 -l 2 \
    --hosts chromeos2-row5-rack4-host6 chromeos4-row12-rack11-host2

    ['chromeos2-row5-rack4-host6', 'chromeos4-row12-rack11-host2']
    found all duts. Time to get host_history.
    usage stats for host: chromeos2-row5-rack4-host6
     2014-07-25 13:02:22 - 2014-07-25 15:02:22
     Num entries found in this interval: 0
            Verifying:        0.00 %
            Running:          0.00 %
            Ready:            100.00 %
            Repairing:        0.00 %
            Repair Failed:    0.00 %
            Cleaning:         0.00 %
            Pending:          0.00 %
            Resetting:        0.00 %
            Provisioning:     0.00 %
            Locked:           0.00 %
    - -- --- ---- ----- ---- --- -- -

    usage stats for host: chromeos4-row12-rack11-host2
     2014-07-25 13:02:22 - 2014-07-25 15:02:22
     Num entries found in this interval: 138
            Verifying:        0.00 %
            Running:          70.45 %
            Ready:            17.79 %
            Repairing:        0.00 %
            Repair Failed:    0.00 %
            Cleaning:         0.00 %
            Pending:          1.24 %
            Resetting:        10.78 %
            Provisioning:     0.00 %
            Locked:           0.00 %
    - -- --- ---- ----- ---- --- -- -
"""

import argparse
import multiprocessing
import multiprocessing.pool
import time
import traceback

import common
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib import time_utils
from autotest_lib.server.cros.dynamic_suite import frontend_wrappers
from autotest_lib.site_utils import host_history_utils
from autotest_lib.site_utils import job_history


AUTOTEST_SERVER = global_config.global_config.get_config_value(
        'SERVER', 'hostname', type=str)


def get_matched_hosts(autotest_server, board, pool):
    """Get duts with matching board and pool labels from given autotest instance

    @param autotest_server: Name of the autotest server, from which we will
                            get all duts.
    @param board: board of DUT, set to None if board doesn't need to match.
    @param pool: pool of DUT, set to None if pool doesn't need to match.
    @return: A list of duts that match the specified board and pool.
    """
    multiple_labels = []
    if pool:
        multiple_labels.append('pool:%s' % pool)
    if board:
        multiple_labels.append('board:%s' % board)
    hosts = []
    afe = frontend_wrappers.RetryingAFE(
            server=autotest_server, timeout_min=60, delay_sec=0)
    for dut in afe.run('get_hosts', multiple_labels=multiple_labels):
        hosts.append(dut['hostname'])
    return hosts


def print_all_stats(results, labels, t_start, t_end):
    """Prints overall stats followed by stats for each host.

    @param results: A list of tuples of three elements.
            1st element: String representing report for individual host.
            2nd element: An ordered dictionary with
                    key as (t_start, t_end) and value as (status, metadata)
                    status = status of the host. e.g. 'Repair Failed'
                    t_start is the beginning of the interval where the DUT's has
                            that status
                    t_end is the end of the interval where the DUT has that
                            status
                    metadata: A dictionary of other metadata, e.g.,
                              {'task_id':123, 'task_name':'Reset'}
            3rd element: hostname of the dut.
    @param labels: A list of labels useful for describing the group
                   of hosts these overall stats represent.
    @param t_start: beginning of time period we are interested in.
    @param t_end: end of time period we are interested in.
    """
    result_strs, stat_intervals_lst, hostname = zip(*results)
    overall_report_str = host_history_utils.get_overall_report(
            labels, t_start, t_end, stat_intervals_lst)
    # Print the overall stats
    print overall_report_str
    # Print the stats for each individual host.
    for result_str in result_strs:
        print result_str


def get_host_history(input):
    """Gets the host history.

    @param input: A dictionary of input arguments to
                  host_history_utils.host_history_stats.
                  Must contain these keys:
                      't_start',
                      't_end',
                      'hostname',
                      'size,'
                      'print_each_interval'
    @returns:
            result_str: String reporting history for specific host.
            stat_intervals: A ordered dictionary with
                    key as (t_start, t_end) and value as (status, metadata)
                    status = status of the host. e.g. 'Repair Failed'
                    t_start is the beginning of the interval where the DUT's has
                            that status
                    t_end is the end of the interval where the DUT has that
                            status
                    metadata: A dictionary of other metadata, e.g.,
                              {'task_id':123, 'task_name':'Reset'}
    """
    try:
        result_str, stat_intervals = host_history_utils.get_report_for_host(
                **input)
        return result_str, stat_intervals, input['hostname']
    except Exception as e:
        # In case any process throws an Exception, we want to see it.
        print traceback.print_exc()
        return None, None, None


def get_log_url(hostname, metadata):
    """Compile a url to job's debug log from debug string.

    @param hostname: Hostname of the dut.
    @param metadata: A dictionary of other metadata, e.g.,
                                     {'task_id':123, 'task_name':'Reset'}
    @return: Url of the debug log for special task or job url for test job.
    """
    log_url = None
    if 'task_id' in metadata and 'task_name' in metadata:
        log_url = job_history.TASK_URL % {'hostname': hostname,
                                          'task_id': metadata['task_id'],
                                          'task_name': metadata['task_name']}
    elif 'job_id' in metadata and 'owner' in metadata:
        log_url = job_history.JOB_URL % {'hostname': hostname,
                                         'job_id': metadata['job_id'],
                                         'owner': metadata['owner']}

    return log_url


def build_history(hostname, status_intervals):
    """Get host history information from given state intervals.

    @param hostname: Hostname of the dut.
    @param status_intervals: A ordered dictionary with
                    key as (t_start, t_end) and value as (status, metadata)
                    status = status of the host. e.g. 'Repair Failed'
                    t_start is the beginning of the interval where the DUT's has
                            that status
                    t_end is the end of the interval where the DUT has that
                            status
                    metadata: A dictionary of other metadata, e.g.,
                                        {'task_id':123, 'task_name':'Reset'}
    @return: A list of host history, e.g.,
             [{'status': 'Resetting'
               'start_time': '2014-08-07 10:02:16',
               'end_time': '2014-08-07 10:03:16',
               'log_url': 'http://autotest/reset-546546/debug',
               'task_id': 546546},
              {'status': 'Running'
               'start_time': '2014-08-07 10:03:18',
               'end_time': '2014-08-07 10:13:00',
               'log_url': 'http://autotest/afe/#tab_id=view_job&object_id=1683',
               'job_id': 1683}
             ]
    """
    history = []
    for time_interval, status_info in status_intervals.items():
        start_time = time_utils.epoch_time_to_date_string(time_interval[0])
        end_time = time_utils.epoch_time_to_date_string(time_interval[1])
        interval = {'status': status_info['status'],
                    'start_time': start_time,
                    'end_time': end_time}
        interval['log_url'] = get_log_url(hostname, status_info['metadata'])
        interval.update(status_info['metadata'])
        history.append(interval)
    return history


def get_results_in_parallel(start_time, end_time,
                            autotest_server=AUTOTEST_SERVER,
                            hosts=None, board=None, pool=None, size=10000,
                            verbose=False, process_pool_size=None):
    """Get history results of specified hosts in parallel.

    If hosts is set to None, all hosts are used, filtered by the board and pool
    constraints. If board is not provided, all boards are included. If pool is
    not provided, all pools are included.
    If a list of hosts is provided, the board and pool constraints are ignored.

    @param autotest_server: Autotest instance name. Default is the server set
                            in global config.
    @param hosts: A list of hosts to search for history. Default is None.
    @param board: board type of hosts. Default is None.
    @param pool: pool type of hosts. Default is None.
    @param start_time: start time to search for history, can be string value or
                       epoch time.
    @param end_time: end time to search for history, can be string value or
                     epoch time.
    @param size: Maximum number of entries to return for ES query, default to
                 10000.
    @param verbose: True to print out detail intervals of host history.
    @param process_pool_size: Number of processes to get results in parallel.
                              Default to None to use the system default pool
                              size.
    @returns: A result object from parallel query for host history.
    """
    assert start_time and end_time
    start_time = time_utils.to_epoch_time(start_time)
    end_time = time_utils.to_epoch_time(end_time)
    assert start_time < end_time

    if not hosts:
        multiple_labels = []
        if pool:
            multiple_labels.append('pool:%s' % pool)
        if board:
            multiple_labels.append('board:%s' % board)
        afe = frontend_wrappers.RetryingAFE(
                server=autotest_server, timeout_min=60, delay_sec=0)
        hosts = [dut['hostname'] for dut in
                 afe.run('get_hosts', multiple_labels=multiple_labels)]
        if not hosts:
            raise Exception('No host found to search for history.')
    print 'Found %d duts. Time to get host_history.' % len(hosts)

    args = []
    for hostname in hosts:
        args.append({'t_start': start_time,
                     't_end': end_time,
                     'hostname': hostname,
                     'size': size,
                     'print_each_interval': verbose,
                     'index': autotest_server})

    # Parallelizing this process.
    pool = multiprocessing.pool.ThreadPool(processes=process_pool_size)
    return pool.imap_unordered(get_host_history, args)


def get_history_details(start_time, end_time, hosts=None, board=None,
                        pool=None, process_pool_size=None):
    """Get the details of host history.

    The return is a dictionary of host history for each host, for example,
    {'172.22.33.51': [{'status': 'Resetting'
                       'start_time': '2014-08-07 10:02:16',
                       'end_time': '2014-08-07 10:03:16',
                       'log_url': 'http://autotest/reset-546546/debug',
                       'task_id': 546546},
                      {'status': 'Running'
                       'start_time': '2014-08-07 10:03:18',
                       'end_time': '2014-08-07 10:13:00',
                       'log_url': ('http://%s/tko/retrieve_logs.cgi?job=/'
                                   'results/16853-debug/172.22.33.51'),
                       'job_id': 16853}
                     ]
    }
    @param start_time: start time to search for history, can be string value or
                       epoch time.
    @param end_time: end time to search for history, can be string value or
                     epoch time.
    @param hosts: A list of hosts to search for history. Default is None.
    @param board: board type of hosts. Default is None.
    @param pool: pool type of hosts. Default is None.
    @param process_pool_size: Number of processes to get results in parallel.
                              Default to None to use the system default pool
                              size.
    @returns: A dictionary of the host history details.
    """
    results = get_results_in_parallel(start_time=start_time, end_time=end_time,
                                      hosts=hosts, board=board, pool=pool,
                                      process_pool_size=process_pool_size)
    all_history = {}
    for result_str, status_intervals, hostname in results:
        if hostname:
            all_history[hostname] = build_history(hostname, status_intervals)
    return all_history


def main():
    """main script. """
    t_now = time.time()
    t_now_minus_one_day = t_now - 3600 * 24
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', type=str, dest='autotest_server',
                        help='Enter Autotest instance name, e.g., "cautotest".',
                        default=AUTOTEST_SERVER)
    parser.add_argument('-v', action='store_true', dest='verbose',
                        default=False,
                        help='-v to print out ALL entries.')
    parser.add_argument('-n', type=int, dest='size',
                        help='Maximum number of entries to return.',
                        default=10000)
    parser.add_argument('-l', type=float, dest='last',
                        help='last hours to search results across',
                        default=None)
    parser.add_argument('--board', type=str, dest='board',
                        help='restrict query by board, not implemented yet',
                        default=None)
    parser.add_argument('--pool', type=str, dest='pool',
                        help='restrict query by pool, not implemented yet',
                        default=None)
    parser.add_argument('--hosts', nargs='+', dest='hosts',
                        help='Enter space deliminated hostnames',
                        default=[])
    parser.add_argument('--start', type=str, dest='start',
                        help=('Enter start time as: yyyy-mm-dd hh:mm:ss,'
                              'defualts to 24h ago.'),
                        default=time_utils.epoch_time_to_date_string(
                                t_now_minus_one_day))
    parser.add_argument('--end', type=str, dest='end',
                        help=('Enter end time in as: yyyy-mm-dd hh:mm:ss,'
                              'defualts to current time.'),
                        default=time_utils.epoch_time_to_date_string(t_now))
    options = parser.parse_args()

    if options.last:
        start_time = t_now - 3600 * options.last
        end_time = t_now
    else:
        start_time = time_utils.to_epoch_time(options.start)
        end_time = time_utils.to_epoch_time(options.end)

    results = get_results_in_parallel(autotest_server=options.autotest_server,
                                      hosts=options.hosts,
                                      board=options.board,
                                      pool=options.pool,
                                      start_time=start_time,
                                      end_time=end_time,
                                      size=options.size,
                                      verbose=options.verbose)
    time.sleep(3)
    labels = []
    if options.board:
        labels.append('board:%s' % (options.board))
    if options.pool:
        labels.append('pool:%s' % (options.pool))
    print_all_stats(results, labels, start_time, end_time)


if __name__ == '__main__':
    main()
