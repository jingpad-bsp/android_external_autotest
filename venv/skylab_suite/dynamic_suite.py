# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module for CrOS dynamic test suite generation and execution."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging

from skylab_suite import suite_waiter


def run(suite_job):
    """Run a CrOS dynamic test suite.

    @param suite_job: A suite.Suite object.
    """
    for test in suite_job.tests:
        schedule(test)

    if suite_job.wait:
        waiter = suite_waiter.SuiteResultWaiter()
        waiter.wait_for_results()


def schedule(test):
    """Schedule a CrOS test.

    @param test: A single test to run, represented by ControlData object.
    """
    logging.info('Scheduling test %s', test.name)
    return
