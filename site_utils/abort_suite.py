#!/usr/bin/python -t
#
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


"""
Usage: ./abort_suite.py [-i and -s you passed to run_suite.py]

This code exists to allow buildbot to abort a HWTest run if another part of
the build fails while HWTesting is going on.  If we're going to fail the
build anyway, there's no point in continuing to run tests.

One can also pass just the build version to -i, to abort all boards running the
suite against that version. ie. |./abort_suite.py -i R28-3993.0.0 -s dummy|
would abort all boards running dummy on R28-3993.0.0.

"""


import argparse
import getpass
import sys

import common
from autotest_lib.server import frontend


SUITE_JOB_NAME_TEMPLATE = '%s-test_suites/control.%s'


def find_jobs_by_name(afe, substring):
    """
    Contact the AFE to find unfinished jobs whose name contain the argument.

    @param afe An instance of frontend.AFE to make RPCs with.
    @param substring The substring to search for in the job name.
    @return List of matching job IDs.

    """
    # We need to avoid pulling back finished jobs, in case an overly general
    # name to match against was passed in.  Unfortunately, we can't pass
    # `not_yet_run` and `running` at the same time, so we do it as two calls.
    # These two calls need to be in this order in case a suite goes from queued
    # to running in between the two calls.
    queued_jobs = afe.run('get_jobs', not_yet_run=True,
                          name__contains=substring, owner=getpass.getuser())
    running_jobs = afe.run('get_jobs', running=True,
                           name__contains=substring, owner=getpass.getuser())
    # If a job does go from queued to running, we'll get it twice, so we need
    # to remove duplicates.  The RPC interface only accepts a list, so it is
    # easiest if we return a list from this function.
    job_ids = [int(job['id']) for job in queued_jobs + running_jobs]
    return list(set(job_ids))


def parse_args():
    """
    Parse the arguments to this script.

    @return The arguments to this script.

    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--suite_name', dest='name')
    parser.add_argument('-i', '--build', dest='build')
    return parser.parse_args()


def abort_jobs(afe, job_ids):
    """
    Abort all of the HQEs associated with the given jobs.

    @param afe An instance of frontend.AFE to make RPCs with.
    @param job_ids A list of ints that are the job id's to abort.
    @return None

    """
    afe.run('abort_host_queue_entries', job_id__in=job_ids)


def main():
    """Main."""
    afe = frontend.AFE()
    args = parse_args()
    name = SUITE_JOB_NAME_TEMPLATE % (args.build, args.name)
    job_ids = find_jobs_by_name(afe, name)
    print "Aborting jobs %s" % ', '.join([str(x) for x in job_ids])
    abort_jobs(afe, job_ids)
    return 0


if __name__ == '__main__':
    sys.exit(main())
