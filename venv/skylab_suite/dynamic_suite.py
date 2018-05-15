# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module for CrOS dynamic test suite generation and execution."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import json
import logging
import os
import time

from lucifer import autotest
from skylab_suite import swarming_lib


SKYLAB_DRONE_POOL = 'ChromeOSSkylab'
SKYLAB_DRONE_SWARMING_WORKER = '/opt/infra-tools/usr/bin/skylab_swarming_worker'


def _make_trigger_swarming_cmd(swarming_client, task_name, dimensions, cmd):
    swarming_cmd = [swarming_client, 'trigger',
                    '--auth-service-account-json', swarming_lib.SERVICE_ACCOUNT,
                    '--swarming', swarming_lib.SWARMING_SERVER,
                    '--task-name', task_name, '--raw-cmd']
    for dimension in dimensions:
        swarming_cmd += ['--dimension', dimension[0], dimension[1]]

    if 'SWARMING_TASK_ID' in os.environ:
        swarming_cmd += ['--tags=%s:%s' % ('parent_task_id',
                                           os.environ['SWARMING_TASK_ID'])]

    swarming_cmd += ['--raw-cmd', '--']
    swarming_cmd += cmd
    return swarming_cmd


def _run_swarming_cmd(swarming_cmd):
    timeout_util = autotest.chromite_load('timeout_util')
    cros_build_lib = autotest.chromite_load('cros_build_lib')
    new_env = os.environ.copy()
    with timeout_util.Timeout(60):
        logging.info('Kicking off the swarming task.')
        result = cros_build_lib.RunCommand(
                swarming_cmd, env=new_env, capture_output=True)


def run(suite_job, dry_run=False):
    """Run a CrOS dynamic test suite.

    @param suite_job: A suite.Suite object.
    """
    for test in suite_job.tests:
        _schedule_test(test, dry_run=dry_run)

    suite_id = os.environ.get('SWARMING_TASK_ID')
    if suite_job.wait and suite_id is not None:
        _wait_for_results(suite_id)


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

    dimensions = [('pool', SKYLAB_DRONE_POOL)]
    swarming_cmd = _make_trigger_swarming_cmd(swarming_client, test.name,
                                         dimensions, cmd)
    _run_swarming_cmd(swarming_cmd)


def _fetch_child_tasks(parent_task_id):
    swarming_cmd = swarming_lib.get_basic_swarming_cmd('query')
    swarming_cmd += ['tasks/list?tags=parent_task_id:%s' % parent_task_id]

    timeout_util = autotest.chromite_load('timeout_util')
    cros_build_lib = autotest.chromite_load('cros_build_lib')
    with timeout_util.Timeout(60):
        logging.info('Fetching the child tasks:')
        child_tasks = cros_build_lib.RunCommand(
                swarming_cmd, capture_output=True)
        return json.loads(child_tasks.output)


def _wait_for_results(parent_task_id):
    """Wait for child tasks to finish and return their results."""
    while True:
        json_output = _fetch_child_tasks(parent_task_id)
        all_tasks = json_output['items']
        finished_tasks = [t for t in all_tasks if t['state'] in
                          swarming_lib.TASK_FINISHED_STATUS]
        logging.info('Found %d finished child tasks', len(finished_tasks))
        if len(finished_tasks) == len(all_tasks):
            break

        time.sleep(30)

    logging.info('Finished to wait for child tasks.')
