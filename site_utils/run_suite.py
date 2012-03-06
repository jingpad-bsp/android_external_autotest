#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool for running suites of tests and waiting for completion.

The desired test suite will be scheduled with autotest, and then
this tool will block until the job is complete, printing a summary
at the end.  Error conditions result in exceptions.

This is intended for use only with Chrome OS test suits that leverage the
dynamic suite infrastructure in server/cros/dynamic_suite.py.
"""

import getpass, optparse, time, sys
import common
from autotest_lib.client.common_lib import global_config
from autotest_lib.server.cros import frontend_wrappers

CONFIG = global_config.global_config

def parse_options():
    usage = "usage: %prog [options] control_file"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-b", "--board", dest="board")
    parser.add_option("-i", "--build", dest="build")
    parser.add_option("-p", "--pool", dest="pool", default=None)
    parser.add_option("-s", "--suite_name", dest="name")
    parser.add_option("-t", "--timeout_min", dest="timeout_min", default=30)
    parser.add_option("-d", "--delay_sec", dest="delay_sec", default=10)
    options, args = parser.parse_args()
    return parser, options, args


def get_pretty_status(status):
    if status == 'GOOD':
        return '[ PASSED ]'
    return '[ FAILED ]'


def status_is_relevant(status):
    """
    Indicates whether the status of a given test is meaningful or not.

    @param status: frontend.TestStatus object to look at.
    @return True if this is a test result worth looking at further.
    """
    return not (status['test_name'].startswith('SERVER_JOB') or
                status['test_name'].startswith('CLIENT_JOB'))


def generate_log_link(anchor, job_string):
    """
    Generate a link to this job's logs, for consumption by buildbot.

    @param anchor: Link anchor text.
    @param job_id: the job whose logs we'd like to link to.
    @return A link formatted for the buildbot log annotator.
    """
    host = CONFIG.get_config_value('SERVER', 'hostname', type=str)
    pattern = CONFIG.get_config_value('CROS', 'log_url_pattern', type=str)
    return "@@@STEP_LINK@%s@%s@@@" % (anchor, pattern % (host, job_string))


def main():
    parser, options, args = parse_options()
    if args or not options.build or not options.board or not options.name:
        parser.print_help()
        return
    afe = frontend_wrappers.RetryingAFE(timeout_min=options.timeout_min,
                                        delay_sec=options.delay_sec)
    job_id = afe.run('create_suite_job',
                     suite_name=options.name,
                     board=options.board,
                     build=options.build,
                     pool=options.pool)
    TKO = frontend_wrappers.RetryingTKO(timeout_min=options.timeout_min,
                                        delay_sec=options.delay_sec)
    # Return code that will be sent back to autotest_rpc_server.py
    code = 0
    while True:
        if not afe.get_jobs(id=job_id, finished=True):
            time.sleep(1)
            continue
        views = TKO.run('get_detailed_test_views', afe_job_id=job_id)
        width = len(max(map(lambda x: x['test_name'], views), key=len)) + 3

        relevant_views = filter(status_is_relevant, views)
        if not relevant_views:
           # The main suite job most likely failed in SERVER_JOB.
           relevant_views = views

        log_links = []
        for entry in relevant_views:
            test_entry = entry['test_name'].ljust(width)
            print "%s%s" % (test_entry, get_pretty_status(entry['status']))
            if entry['status'] != 'GOOD':
                print "%s  %s: %s" % (test_entry,
                                      entry['status'],
                                      entry['reason'])
                job_name = entry['test_name'].split('.')[0]
                if 'job_keyvals' in entry and job_name in entry['job_keyvals']:
                    job_name = entry['job_keyvals'][job_name]
                else:
                  # We are the main suite job since there is no keyval entry
                  # for our job_name.
                  job_name = '%s-%s' % (job_id, getpass.getuser())

                log_links.append(generate_log_link(entry['test_name'],
                                                   job_name))
                code = 1
        for link in log_links:
            print link
        break
    return code

if __name__ == "__main__":
    sys.exit(main())
