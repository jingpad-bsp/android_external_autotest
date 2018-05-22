# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module for CrOS dynamic test suite generation and execution."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import collections
import json
import logging
import os
import time

from lucifer import autotest
from skylab_suite import swarming_lib


SKYLAB_DRONE_POOL = 'ChromeOSSkylab'
SKYLAB_DRONE_SWARMING_WORKER = '/opt/infra-tools/usr/bin/skylab_swarming_worker'
RetryTestSpecs= collections.namedtuple(
        'RetryTestSpecs',
        [
                'test',
                'remain_retries',
        ])


def run(tests, retry_handler, dry_run=False):
    """Run a CrOS dynamic test suite.

    @param retry_handler: A cros_suite.RetryHandler object.
    @param dry_run: Whether to kick off dry runs of the tests.
    """
    suite_id = os.environ.get('SWARMING_TASK_ID')
    for test in tests:
        test_task_id = _schedule_test(test, suite_id=suite_id, dry_run=dry_run)
        retry_handler.task_to_test_maps[test_task_id] = RetryTestSpecs(
                test=test, remain_retries=test.job_retries - 1)

    if suite_id is not None and retry_handler.wait:
        retry_handler.suite_id = suite_id
        _wait_for_results(retry_handler, dry_run=dry_run)


def _make_trigger_swarming_cmd(swarming_client, suite_id, task_name,
                               temp_json_path, dimensions, cmd):
    """Form the swarming cmd.

    @param swarming_client: The swarming client script.
    @param suite_id: The suite id of the test to kick off.
    @param task_name: The task name of this swarming command.
    @param temp_json_path: The json file to dump the swarming output.
    @param dimensions: The dimensions of this swarming command.
    @param cmd: The raw command to run in lab.

    @return a string swarming command to kick off.
    """
    swarming_cmd = [swarming_client, 'trigger',
                    '--auth-service-account-json', swarming_lib.SERVICE_ACCOUNT,
                    '--swarming', swarming_lib.SWARMING_SERVER,
                    '--task-name', task_name,
                    '--dump-json', temp_json_path, '--raw-cmd']
    for dimension in dimensions:
        swarming_cmd += ['--dimension', dimension[0], dimension[1]]

    if suite_id is not None:
        swarming_cmd += ['--tags=%s:%s' % ('parent_task_id', suite_id)]

    swarming_cmd += ['--raw-cmd', '--']
    swarming_cmd += cmd
    return swarming_cmd


def _run_swarming_cmd(swarming_cmd, task_name, temp_json_path):
    """Kick off a swarming cmd.

    @param swarming_cmd: The swarming command to run.
    @param task_name: The task name of this swarming command.
    @param temp_json_path: The json file to dump the swarming output.

    @return the swarming task id of this task.
    """
    timeout_util = autotest.chromite_load('timeout_util')
    cros_build_lib = autotest.chromite_load('cros_build_lib')
    new_env = os.environ.copy()
    with timeout_util.Timeout(60):
        cros_build_lib.RunCommand(swarming_cmd, env=new_env)
        with open(temp_json_path) as f:
            result = json.load(f)
            return result['tasks'][task_name]['task_id']


def _schedule_test(test, suite_id=None, dry_run=False):
    """Schedule a CrOS test.

    @param test: A single test to run, represented by ControlData object.
    @param suite_id: the suite task id of the test.
    @param dry_run: Whether to kick off a dry run of a swarming cmd.

    @return the swarming task id of this task.
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

    osutils = autotest.chromite_load('osutils')
    with osutils.TempDir() as tempdir:
        temp_json_path = os.path.join(tempdir, 'temp_summary.json')
        swarming_cmd = _make_trigger_swarming_cmd(
                swarming_client, suite_id, test.name, temp_json_path,
                dimensions, cmd)
        return _run_swarming_cmd(swarming_cmd, test.name, temp_json_path)


def _fetch_child_tasks(parent_task_id):
    """Get the child tasks based on a parent swarming task id.

    @param parent_task_id: The parent swarming task id.

    @return the json output of all child tasks of the given parent task.
    """
    swarming_cmd = swarming_lib.get_basic_swarming_cmd('query')
    swarming_cmd += ['tasks/list?tags=parent_task_id:%s' % parent_task_id]
    timeout_util = autotest.chromite_load('timeout_util')
    cros_build_lib = autotest.chromite_load('cros_build_lib')
    with timeout_util.Timeout(60):
        logging.info('Checking child tasks:')
        child_tasks = cros_build_lib.RunCommand(
                swarming_cmd, capture_output=True)
        return json.loads(child_tasks.output)


def _wait_for_results(retry_handler, dry_run=False):
    """Wait for child tasks to finish and return their results.

    @param retry_handler: a cros_suite.RetryHandler object.
    """
    timeout_util = autotest.chromite_load('timeout_util')
    with timeout_util.Timeout(retry_handler.timeout_mins * 60):
        while True:
            json_output = _fetch_child_tasks(retry_handler.suite_id)
            retry_handler.handle_results(json_output['items'])
            for t in retry_handler.retried_tasks:
                _retry_test(retry_handler, t['task_id'], dry_run=dry_run)

            if retry_handler.finished_waiting():
                break

            time.sleep(30)

    logging.info('Finished to wait for child tasks.')


def _retry_test(retry_handler, task_id, dry_run=False):
    """Retry test for a suite.

    We will execute the following actions for retrying a test:
        1. Schedule the test.
        2. Add the test with the new swarming task id to the suite's
           retry handler, but reduce its remaining retries by 1.
        3. Reduce the suite-level max retries by 1.
        4. Remove prevous failed test from retry handler since it's not
           actively monitored by the suite.

    @param retry_handler: a cros_suite.RetryHandler object.
    @param task_id: The swarming task id for the retried test.
    @param dry_run: Whether to retry a dry run of the test.
    """
    last_retry_specs = retry_handler.task_to_test_maps[task_id]
    logging.info('Retrying test %s, remaining %d retries.',
                 last_retry_specs.test.name,
                 last_retry_specs.remain_retries - 1)
    retried_task_id = _schedule_test(
            last_retry_specs.test,
            suite_id=retry_handler.suite_id,
            dry_run=dry_run)
    retry_handler.task_to_test_maps[retried_task_id] = RetryTestSpecs(
            test=last_retry_specs.test,
            remain_retries=last_retry_specs.remain_retries - 1)
    retry_handler.max_retries -= 1
    retry_handler.task_to_test_maps.pop(task_id, None)
