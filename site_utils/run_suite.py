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
import logging
from autotest_lib.client.common_lib import global_config
from autotest_lib.server.cros import frontend_wrappers
from autotest_lib.client.common_lib import logging_config, logging_manager

CONFIG = global_config.global_config
# This is the prefix that is used to denote an experimental test.
EXPERIMENTAL_PREFIX = 'experimental_'


class RunSuiteLoggingConfig(logging_config.LoggingConfig):
    def configure_logging(self, verbose=False):
        super(RunSuiteLoggingConfig, self).configure_logging(use_console=True)


def parse_options():
    usage = "usage: %prog [options] control_file"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-b", "--board", dest="board")
    parser.add_option("-i", "--build", dest="build")
    #  This should just be a boolean flag, but the autotest "proxy" code
    #  can't handle flags that don't take arguments.
    parser.add_option("-n", "--no_wait", dest="no_wait", default=None)
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

def is_fail_status(status):
    # All the statuses tests can have when they fail.
    if status in ['FAIL', 'ERROR', 'TEST_NA']:
        return True
    return False


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


def suite_job_id(main_job_id, view):
    """
    Parse a view for the slave job name and job_id.

    @param main_job_id: The job id of our master suite job.
    @param view: Test result view.
    @return A tuple job_name, experimental of the slave test run
            described by view.
    """
    # By default, we are the main suite job since there is no
    # keyval entry for our job_name.
    job_name = '%s-%s' % (main_job_id, getpass.getuser())
    experimental = False
    if 'job_keyvals' in view:
        # The job name depends on whether it's experimental or not.
        std_job_name = view['test_name'].split('.')[0]
        exp_job_name = EXPERIMENTAL_PREFIX + std_job_name
        if std_job_name in view['job_keyvals']:
            job_name = view['job_keyvals'][std_job_name]
        elif exp_job_name in view['job_keyvals']:
            experimental = True
            job_name = view['job_keyvals'][exp_job_name]
    return job_name, experimental


def main():
    parser, options, args = parse_options()
    if args or not options.build or not options.board or not options.name:
        parser.print_help()
        return

    logging_manager.configure_logging(RunSuiteLoggingConfig())

    afe = frontend_wrappers.RetryingAFE(timeout_min=options.timeout_min,
                                        delay_sec=options.delay_sec)

    wait = options.no_wait is None

    job_id = afe.run('create_suite_job',
                     suite_name=options.name,
                     board=options.board,
                     build=options.build,
                     check_hosts=wait,
                     pool=options.pool)
    TKO = frontend_wrappers.RetryingTKO(timeout_min=options.timeout_min,
                                        delay_sec=options.delay_sec)
    # Return code that will be sent back to autotest_rpc_server.py
    # 0 = OK
    # 1 = ERROR
    # 2 = WARNING
    code = 0
    while wait and True:
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
                job_name, experimental = suite_job_id(job_id, entry)

                log_links.append(generate_log_link(entry['test_name'],
                                                   job_name))
                if code == 1:
                    # Failed already, no need to worry further.
                    continue
                if (entry['status'] == 'WARN' or
                    (is_fail_status(entry['status']) and experimental)):
                    # Failures that produce a warning. Either a test with WARN
                    # status or any experimental test failure.
                    code = 2
                else:
                    code = 1
        for link in log_links:
            print link
        break
    else:
        print "Created suite job: %r" % job_id
        print generate_log_link(options.name,
                                '%s-%s' % (job_id, getpass.getuser()))
        print "--no_wait specified; Exiting."
    return code

if __name__ == "__main__":
    sys.exit(main())
