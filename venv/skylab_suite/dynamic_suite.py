# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module for CrOS dynamic test suite generation and execution."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging
import os

from lucifer import autotest
from skylab_suite import suite_waiter

SERVICE_ACCOUNT = '/creds/skylab_swarming_bot/skylab_bot_service_account.json'
SWARMING_SERVER = 'chrome-swarming.appspot.com'
SKYLAB_DRONE_SWARMING_WORKER = '/opt/infra-tools/usr/bin/skylab_swarming_worker'
SKYLAB_DRONE_POOL = 'ChromeOSSkylab'


def _make_trigger_swarming_cmd(swarming_client, task_name, dimensions, cmd):
    swarming_cmd = [swarming_client, 'trigger',
                    '--auth-service-account-json', SERVICE_ACCOUNT,
                    '--swarming', SWARMING_SERVER,
                    '--task-name', task_name, '--raw-cmd']
    for dimension in dimensions:
        swarming_cmd += ['--dimension', dimension[0], dimension[1]]

    if 'SWARMING_TASK_ID' in os.environ:
        swarming_cmd += ['--tags=%s:%s' % ('parent_task_id',
                                           os.environ['SWARMING_TASK_ID'])]

    swarming_cmd += ['--']
    swarming_cmd += cmd
    return swarming_cmd


def _run_swarming_cmd(swarming_cmd):
    timeout_util = autotest.chromite_load('timeout_util')
    cros_build_lib = autotest.chromite_load('cros_build_lib')
    new_env = os.environ.copy()
    with timeout_util.Timeout(60):
        logging.info('Kicking off swarming task')
        result = cros_build_lib.RunCommand(swarming_cmd, env=new_env)
        logging.info(result)


def run(suite_job, dry_run=False):
    """Run a CrOS dynamic test suite.

    @param suite_job: A suite.Suite object.
    """
    for test in suite_job.tests:
        _schedule_test(test, dry_run=dry_run)

    if suite_job.wait:
        waiter = suite_waiter.SuiteResultWaiter()
        waiter.wait_for_results()


def _schedule_test(test, dry_run=False):
    """Schedule a CrOS test.

    @param test: A single test to run, represented by ControlData object.
    """
    logging.info('Scheduling test %s', test.name)
    swarming_client = os.path.join(
            os.path.expanduser('~'),
            'chromiumos/chromite/third_party/swarming.client/swarming.py')
    cmd = [SKYLAB_DRONE_SWARMING_WORKER, '-client-test', '-task-name',
               test.name]
    if dry_run:
        cmd = ['/bin/echo'] + cmd
        test.name = 'Echo ' + test.name

    dimensions = [('pool', SKYLAB_DRONE_POOL), ('dut_status', 'ready')]
    swarming_cmd = _make_trigger_swarming_cmd(swarming_client, test.name,
                                         dimensions, cmd)
    _run_swarming_cmd(swarming_cmd)
