#!/usr/bin/env python
# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Generate a report on a given suite run."""

from __future__ import print_function

import common
import sys

from autotest_lib.server.cros.dynamic_suite import frontend_wrappers
from autotest_lib.server.lib import suite_report
from chromite.lib import commandline
from chromite.lib import cros_logging as logging
from chromite.lib import ts_mon_config

def GetParser():
    """Creates the argparse parser."""
    parser = commandline.ArgumentParser(description=__doc__)
    parser.add_argument('job_ids', type=int, nargs='+',
                        help='Suite job ids to dump')
    # As a provision suite may exit before its all provision jobs finish, the
    # provision suite report may not contain all the provision jobs. This hack
    # helps to dump report for all provision jobs under the given provision
    # suite (provision-job-id). See more details in crbug.com/794346
    parser.add_argument('--provision-job-id', type=int,
                        help='Provision suite job id to dump report.')
    parser.add_argument('--output', '-o', type=str, action='store',
                        help='Path to write JSON file to')
    parser.add_argument('--afe', type=str, action='store',
                        help='AFE server to connect to')
    return parser


def main(argv):
    """Standard main() for command line processing.

    @param argv Command line arguments (normally sys.argv).
    """

    parser = GetParser()
    options = parser.parse_args(argv[1:])

    with ts_mon_config.SetupTsMonGlobalState('dump_suite_report'):

        afe = frontend_wrappers.RetryingAFE(timeout_min=5, delay_sec=10,
                                            server=options.afe)
        tko = frontend_wrappers.RetryingTKO(timeout_min=5, delay_sec=10)

        job_ids = set(options.job_ids)
        if options.provision_job_id:
            job_ids.add(options.provision_job_id)

        # Look up and generate entries for all jobs.
        entries = []
        for suite_job_id in job_ids:
            reset_finish_time = (suite_job_id == options.provision_job_id)

            logging.debug('Suite job %s:' % suite_job_id)
            suite_entries = suite_report.generate_suite_report(
                suite_job_id, afe=afe, tko=tko,
                reset_finish_time=reset_finish_time)
            logging.debug('... generated %d entries' % len(suite_entries))
            entries.extend(suite_entries)

        # Write all entries as JSON.
        if options.output:
            with open(options.output, 'w') as f:
                suite_report.dump_entries_as_json(entries, f)
        else:
            suite_report.dump_entries_as_json(entries, sys.stdout)


if __name__ == '__main__':
    main(sys.argv)
