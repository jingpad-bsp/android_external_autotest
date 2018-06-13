# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Wrapper for aborting suites of tests.

Usage: ./abort_suite.py

This code exists to allow buildbot to abort a HWTest run if another part of
the build fails while HWTesting is going on.  If we're going to fail the
build anyway, there's no point in continuing to run tests.

This script aborts suite job and its children jobs.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging
import sys

from lucifer import autotest
from skylab_suite import suite_parser
from skylab_suite import suite_tracking
from skylab_suite import swarming_lib


def _abort_suite(suite_specs, abort_limit):
    """Abort the suite.

    This method aborts the suite job and its children jobs, including
    'RUNNING' jobs.
    """
    tags = {'pool': swarming_lib.SKYLAB_SUITE_POOL,
            'board': suite_specs.board,
            'build': suite_specs.test_source_build,
            'suite': suite_specs.suite_name}
    parent_tasks = swarming_lib.query_task_by_tags(tags)

    aborted_suite_num = 0
    for pt in parent_tasks:
        logging.info('Aborting suite task %s', pt['task_id'])
        swarming_lib.abort_task(pt['task_id'])
        for ct in pt['children_task_ids']:
            logging.info('Aborting task %s', ct)
            swarming_lib.abort_task(ct)

        aborted_suite_num += 1
        if aborted_suite_num >= abort_limit:
            break

    logging.info('Suite %s/%s has been aborted.', suite_specs.test_source_build,
                 suite_specs.suite_name)


def parse_args():
    """Parse and validate skylab suite args."""
    parser = suite_parser.make_parser()
    options = parser.parse_args()
    if not suite_parser.verify_and_clean_options(options):
        parser.print_help()
        sys.exit(1)

    return options


def main():
    """Entry point."""
    autotest.monkeypatch()

    options = parse_args()
    suite_tracking.setup_logging()
    suite_specs = suite_parser.parse_suite_specs(options)
    _abort_suite(suite_specs, options.abort_limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
