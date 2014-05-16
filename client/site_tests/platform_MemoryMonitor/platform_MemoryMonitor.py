# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'namnguyen@chromium.org'

import collections
import itertools
import logging
import operator
import re

from autotest_lib.client.bin import utils, test


GeneralUsage = collections.namedtuple('GeneralUsage', 'total used free')
ProcessUsage = collections.namedtuple('ProcessUsage', 'pid user virtual '
    'resident shared command')  # command does NOT have arguments


def parse_mem(s):
    """Extracts a number out of a string such as 467m, 123k, 999g.

    @param s: a string to parse

    @return a float that s represents
    """

    multipliers = {'k': 1024, 'm': 1024**2, 'g': 1024**3}

    multiplier = multipliers.get(s[-1], 1)
    if multiplier != 1:
        s = s[:-1]

    return float(s) * multiplier


def parse_general_usage(line):
    """Extracts general memory usage from a line from top.

    @param line: string a general memory consumption line from top

    @return a GeneralUsage tuple
    """

    items = re.search(
        r'\s+(\d+) total,\s+(\d+) used,\s+(\d+) free', line).groups()
    return GeneralUsage(*[float(x) for x in items])


def parse_process_usage(line, headers):
    """Extracts memory usage numbers from a process line from top.

    @param line: string a process line from `top`
    @param headers: array of strings naming each field in the line

    @return a ProcessUsage tuple
    """

    interested_fields = {
        'pid': ('pid', int),
        'user': ('user', str),
        'virt': ('virtual', parse_mem),
        'res': ('resident', parse_mem),
        'shr': ('shared', parse_mem),
        'command': ('command', str),
    }

    fields = line.split()
    current_interest_idx = 0
    record = {}
    for i, field in enumerate(fields):
        if headers[i] not in interested_fields:
            continue
        key, extractor = interested_fields[headers[i]]
        record[key] = extractor(field)

    return ProcessUsage(**record)


def parse_processes(lines):
    """Extracts information about processes from `top`.

    @param lines: a list of lines from top, the header must be the first
        entry in this list
    @return a list of ProcessUsage
    """

    headers = [x.lower() for x in lines[0].split()]
    processes = []
    for line in lines[1:]:
        process_usage = parse_process_usage(line, headers)
        if process_usage.command.startswith('autotest'):
            continue
        processes.append(process_usage)
        logging.debug('Process usage: %r', process_usage)
    return processes


def report_top_processes(processes, n=10):
    """Returns a dictionary of top n processes.

    For example:
        {
            'top_1': 4000,
            'top_2': 3000,
            'top_3': 2500,
        }

    @param processes: a list of ProcessUsage
    @param n: maximum number of processes to return
    @return dictionary whose key correlate to the ranking, and values are
        amount of resident memory
    """

    get_resident = operator.attrgetter('resident')
    top_users = sorted(processes, key=get_resident, reverse=True)
    logging.info('Top 10 memory users:')
    perf_values = {}
    for i, process in enumerate(top_users[:n]):
        logging.info('%r', process)
        perf_values['top_%d' % (i + 1)] = process.resident
    return perf_values


def group_by_command(processes):
    """Returns resident memory of processes with the same command.

    For example:
        {
            'process_shill': 20971520,
            'process_sshd': 4792,
        }

    @param processes: a list of ProcessUsage
    @return dictionary whose keys correlate to the command line, and values
        the sum of resident memory used by all processes with the same
        command
    """

    get_command = operator.attrgetter('command')
    sorted_by_command = sorted(processes, key=get_command)
    grouped_by_command = itertools.groupby(sorted_by_command,
                                           key=get_command)
    top_by_command = []
    for command, grouped_processes in grouped_by_command:
        resident=sum(p.resident for p in grouped_processes)
        top_by_command.append((resident, command))
    top_by_command.sort(reverse=True)
    logging.info('Top processes by sum of memory consumption:')
    perf_values = {}
    for resident, command in top_by_command:
        command = command.replace(':', '_').replace('/', '_')
        logging.info('Command: %s, Resident: %f', command, resident)
        perf_values['process_%s' % command] = resident
    return perf_values


def group_by_service(processes):
    """Returns a collection of startup services and their memory usage.

    For example:
        {
            'service_chapsd': 6568,
            'service_cras': 3788,
            'service_ui': 329284024
        }

    @param processes: a list of ProcessUsage
    @returns dictionary whose keys correlate to the service name, and
        values are sum of resident memory used by that service
    """

    processes = dict((p.pid, p.resident) for p in processes)
    top_by_service = []
    initctl = utils.system_output('initctl list')
    logging.debug('Service list:\n%s', initctl)
    for line in initctl.split('\n'):
        if 'process' not in line:
            continue
        fields = line.split()
        service, main_process = fields[0], int(fields[3])
        resident = 0
        pstree = utils.system_output('pstree -p %d' % main_process)
        logging.debug('Service %s:\n%s', service, pstree)
        for pid in re.findall(r'\((\d+)\)', pstree, re.MULTILINE):
            pid = int(pid)
            logging.debug('Summing process %d', pid)
            resident += processes.get(pid, 0)
        top_by_service.append((resident, service))
    top_by_service.sort(reverse=True)
    logging.info('Top services:')
    perf_values = {}
    for resident, service in top_by_service:
        logging.info('Service: %s, Resident: %f', service, resident)
        perf_values['service_%s' % service] = resident
    return perf_values


class platform_MemoryMonitor(test.test):
    """Monitor memory usage trend."""

    version = 1

    def run_once(self):
        cmd = 'top -b -n 1'
        output = utils.system_output(cmd)
        logging.debug('Output from top:\n%s', output)
        lines = output.split('\n')
        # Ignore the first 3 lines, they're not relevant in this test.
        lines = lines[3:]
        mem_general = parse_general_usage(lines[0])
        logging.info('Total, used, and free memory (in KiB): %r, %r, %r',
                     *mem_general)
        swap_general = parse_general_usage(lines[1])
        logging.info('Total, used, and free swap (in KiB): %r, %r, %r',
                     *swap_general)

        perf_values = {
            'mem_total': mem_general.total * 1024,
            'mem_used': mem_general.used * 1024,
            'mem_free': mem_general.free * 1024,
            'swap_total': swap_general.total * 1024,
            'swap_used': swap_general.used * 1024,
            'swap_free': swap_general.free * 1024,
        }

        # Ignore general mem, swap and a blank line.
        lines = lines[3:]

        processes = parse_processes(lines)
        perf_values.update(report_top_processes(processes))
        perf_values.update(group_by_command(processes))
        perf_values.update(group_by_service(processes))

        for key, val in perf_values.items():
            graph_name = key.split('_')[0]
            self.output_perf_value(key, val, units="bytes",
                higher_is_better=False, graph=graph_name)
        self.write_perf_keyval(perf_values)
