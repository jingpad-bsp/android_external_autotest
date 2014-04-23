#! /usr/bin/python

"""Chronological analysis of special tasks on a host.

Usage:
    To analyze all special tasks that ran after/before a given job:
        onerous_tasks.py job_id -id 123 -cutoff 5

    To analyze all special tasks that ran on a host between 4-5 pm on 3/25/2014:
        onerous_tasks.py host -host 123.123\
            -start "2014-03-25 16:00:00" -end "2014-03-25 17:00:00

One can use the script to get host history information, figure out what jobs ran
after/before a failed SERVER_JOB, or just add clarity to jobs running on hosts.
"""


import argparse
import datetime as datetime_base
from datetime import datetime
import logging
import sys

import common
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.afe import models
from autotest_lib.server.cros.dynamic_suite import job_status


TASK_LOGS = ('http://cautotest/tko/retrieve_logs.cgi?job=/results/hosts/'
             '%(hostname)s/%(task_id)s-%(taskname)s')


def _parse_args(args):
    description=('onerous_tasks.py job_id -id 123 -cutoff 5 or \n'
                 'onerous_tasks.py host -host 123.123 '
                 '-start "2014-03-25 16:26:31" -end "2014-03-25 16:26:31"\n')
    if not args:
        print ('Too few arguments, execute \n%s\nor try '
               './onerous_tasks.py --help' % description)
        sys.exit(1)

    parser = argparse.ArgumentParser(
            description='A script to get the special tasks on a host or job.')
    subparsers = parser.add_subparsers(help='Get tasks based on a job or host.')
    parser_job = subparsers.add_parser('job', help='Per Job analysis mode.')
    parser_job.set_defaults(which='job')
    parser_job.add_argument('-id', help='job_id.')
    parser_job.add_argument('-cutoff', default=5, type=int,
                            help='Hours after the job.')
    parser_host = subparsers.add_parser('host', help='Per host analysis mode.')
    parser_host.set_defaults(which='host')
    parser_host.add_argument('-name',
                             help='Hostname for which you would like tasks.')
    parser_host.add_argument(
            '-start', help='Start time. Eg: 2014-03-25 16:26:31')
    parser_host.add_argument(
            '-end', help='End time Eg: 2014-03-25 18:26:31.')
    return parser.parse_args(args)


def get_logs_for_tasks(task_ids):
    """Get links to the logs for the given task ids."""
    tasks = models.SpecialTask.objects.filter(id__in=task_ids)
    task_logs = {}
    for task in tasks:
        task_dict = {'hostname': task.host.hostname,
                     'task_id': task.id,
                     'taskname': task.task.lower()}
        task_logs[task.id] = TASK_LOGS % task_dict
    return task_logs


def _tasks_with_filter(**task_filter):
    """Get tasks applying a filter."""
    tasks = models.SpecialTask.objects.filter(**task_filter)
    task_logs = get_logs_for_tasks([task.id for task in tasks])
    for task in tasks:
        task_dict = {'task': task.task, 'id': task.id,
                     'hqe': task.queue_entry_id,
                     'job': task.queue_entry.job_id if task.queue_entry else None,
                     'host': task.host.hostname,
                     'status': 'Passed' if task.success else 'Failed',
                     'logs': task_logs[task.id], 'time': task.time_started}
        print ('\t%(task)s (%(id)s), for (hqe %(hqe)s, job %(job)s) at '
               '%(time)s [%(status)s]: %(logs)s' % task_dict)


def lookup_host(hostname, start, end):
    """Lookup tasks on a host, within the start and end times."""
    _tasks_with_filter(
            host__hostname=hostname, time_started__gte=start, time_started__lte=end)


def lookup_job(job_id, cutoff=5, taskname=None, success=None):
    """Lookup tasks on a job, within cutoff of the job's start time."""
    hqe = models.HostQueueEntry.objects.filter(job_id=job_id)
    if len(hqe) > 1:
        logging.error('Support for jobs with multiple hqes not implemented. '
                      '%s is one such job.', job_id)
        return
    hqe = hqe[0]

    cutoff = hqe.started_on + datetime_base.timedelta(hours=cutoff)
    print '\nThe tasks before the job were:\n'
    lookup_host(hqe.host.hostname, hqe.started_on - datetime_base.timedelta(minutes=5),
                hqe.started_on)
    print ('\nJob %s (%s), started on %s on %s. Getting tasks before %s\n' %
           (hqe.job.name, job_id, hqe.host.hostname, hqe.started_on, cutoff))
    print '\nThe tasks after the job were:\n'
    lookup_host(hqe.host.hostname, hqe.started_on, cutoff)


if __name__ == '__main__':
    args = _parse_args(sys.argv[1:])
    if args.which == 'job':
        lookup_job(args.id, args.cutoff)
    elif args.which == 'host':
        lookup_host(args.name,
                    datetime.strptime(args.start, job_status.TIME_FMT),
                    datetime.strptime(args.end, job_status.TIME_FMT))
    else:
        print 'Unrecognized options. Try onerous_tasks.py --help'
