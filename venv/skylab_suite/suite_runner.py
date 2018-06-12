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
from skylab_suite import cros_suite
from skylab_suite import swarming_lib


SKYLAB_SUITE_USER = 'skylab_suite_runner'
SKYLAB_LUCI_TAG = 'luci_project:chromiumos'
SKYLAB_DRONE_POOL = 'ChromeOSSkylab'
SKYLAB_DRONE_SWARMING_WORKER = '/opt/infra-tools/usr/bin/skylab_swarming_worker'


def run(tests_specs, suite_handler, dry_run=False):
    """Run a CrOS dynamic test suite.

    @param tests_specs: A list of cros_suite.TestSpecs objects.
    @param suite_handler: A cros_suite.SuiteHandler object.
    @param dry_run: Whether to kick off dry runs of the tests.
    """
    suite_id = os.environ.get('SWARMING_TASK_ID')
    for test_specs in tests_specs:
        test_task_id = _schedule_test(
                test_specs,
                suite_handler.is_provision(),
                suite_id=suite_id,
                dry_run=dry_run)
        suite_handler.add_test_by_task_id(
                test_task_id,
                cros_suite.TestHandlerSpecs(
                        test_specs=test_specs,
                        remaining_retries=test_specs.test.job_retries - 1,
                        previous_retried_ids=[]))

    if suite_id is not None and suite_handler.should_wait():
        suite_handler.set_suite_id(suite_id)
        _wait_for_results(suite_handler, dry_run=dry_run)


def _make_provision_swarming_cmd():
    basic_swarming_cmd = swarming_lib.get_basic_swarming_cmd('post')
    return basic_swarming_cmd + ['tasks/new']


def _make_trigger_swarming_cmd(cmd, dimensions, test_specs,
                               temp_json_path, suite_id):
    """Form the swarming cmd.

    @param cmd: The raw command to run in lab.
    @param dimensions: A dict of dimensions used to form the swarming cmd.
    @param test_specs: a cros_suite.TestSpecs object.
    @param temp_json_path: The json file to dump the swarming output.
    @param suite_id: The suite id of the test to kick off.

    @return a string swarming command to kick off.
    """
    basic_swarming_cmd = swarming_lib.get_basic_swarming_cmd('trigger')
    swarming_cmd = basic_swarming_cmd + [
            '--task-name', test_specs.test.name,
            '--dump-json', temp_json_path,
            '--hard-timeout', str(test_specs.execution_timeout_secs),
            '--io-timeout', str(test_specs.io_timeout_secs),
            '--raw-cmd']

    swarming_cmd += ['--tags=%s' % SKYLAB_LUCI_TAG]
    for k, v in dimensions.iteritems():
        swarming_cmd += ['--dimension', k, v]

    if suite_id is not None:
        swarming_cmd += ['--tags=%s:%s' % ('parent_task_id', suite_id)]

    swarming_cmd += ['--raw-cmd', '--']
    swarming_cmd += cmd
    return swarming_cmd


def _get_suite_cmd(test_specs, is_provision=False):
    """Get the command for running a suite.

    @param test_specs: a cros_suite.TestSpecs object.
    @param is_provision: whether the command is for provision.
    """
    cmd = [SKYLAB_DRONE_SWARMING_WORKER, '-client-test', '-task-name',
           test_specs.test.name]
    if is_provision:
        cmd += ['-provision-labels', 'cros-version:%s' % test_specs.build]

    return cmd


def _run_provision_cmd(cmd, dimensions, test_specs, suite_id):
    """Kick off a provision swarming cmd.

    @param cmd: The raw command to run in lab.
    @param dimensions: A dict of dimensions used to form the swarming cmd.
    @param test_specs: a cros_suite.TestSpecs object.
    @param suite_id: The suite id of the test to kick off.
    """
    normal_dimensions = dimensions.copy()
    normal_dimensions['provisionable-cros-version'] = test_specs.build
    all_dimensions = [normal_dimensions, dimensions]
    tags = [SKYLAB_LUCI_TAG, 'build:%s' % test_specs.build]
    if suite_id is not None:
        tags += ['parent_task_id:%s' % suite_id]

    json_request = swarming_lib.make_fallback_request_dict(
            cmds=[cmd] * len(all_dimensions),
            slices_dimensions=all_dimensions,
            task_name=test_specs.test.name,
            priority=test_specs.priority,
            tags=tags,
            user=SKYLAB_SUITE_USER,
            expiration_secs=test_specs.expiration_secs,
            grace_period_secs=test_specs.grace_period_secs,
            execution_timeout_secs=test_specs.execution_timeout_secs,
            io_timeout_secs=test_specs.io_timeout_secs)

    cros_build_lib = autotest.chromite_load('cros_build_lib')
    provision_cmd = _make_provision_swarming_cmd()
    result = cros_build_lib.RunCommand(provision_cmd,
                                       input=json.dumps(json_request),
                                       env=os.environ.copy(),
                                       capture_output=True)
    logging.info('Input: %r', json_request)
    return json.loads(result.output)['task_id']


def _run_swarming_cmd(cmd, dimensions, test_specs, temp_json_path, suite_id):
    """Kick off a swarming cmd.

    @param cmd: The raw command to run in lab.
    @param dimensions: A dict of dimensions used to form the swarming cmd.
    @param test_specs: a cros_suite.TestSpecs object.
    @param temp_json_path: The json file to dump the swarming output.
    @param suite_id: The suite id of the test to kick off.

    @return the swarming task id of this task.
    """
    # TODO (xixuan): Add this to provision cmd when cron job for special task
    # is working.
    dimensions['dut_state'] = swarming_lib.SWARMING_DUT_READY_STATUS
    trigger_cmd = _make_trigger_swarming_cmd(cmd, dimensions, test_specs,
                                             temp_json_path, suite_id)
    cros_build_lib = autotest.chromite_load('cros_build_lib')
    new_env = os.environ.copy()
    cros_build_lib.RunCommand(trigger_cmd, env=new_env)
    with open(temp_json_path) as f:
        result = json.load(f)
        return result['tasks'][test_specs.test.name]['task_id']


def _schedule_test(test_specs, is_provision, suite_id=None,
                   dry_run=False):
    """Schedule a CrOS test.

    @param test_specs: A cros_suite.TestSpec object.
    @param is_provision: A boolean, whether to kick off a provision test.
    @param suite_id: the suite task id of the test.
    @param dry_run: Whether to kick off a dry run of a swarming cmd.

    @return the swarming task id of this task.
    """
    logging.info('Scheduling test %s', test_specs.test.name)
    cmd = _get_suite_cmd(test_specs, is_provision=is_provision)
    if dry_run:
        cmd = ['/bin/echo'] + cmd
        test_specs.test.name = 'Echo ' + test_specs.test.name

    dimensions = {'pool':SKYLAB_DRONE_POOL,
                  'label-pool': swarming_lib.SWARMING_DUT_POOL_MAP.get(
                          test_specs.pool),
                  'label-board': test_specs.board}

    osutils = autotest.chromite_load('osutils')
    with osutils.TempDir() as tempdir:
        temp_json_path = os.path.join(tempdir, 'temp_summary.json')
        if is_provision:
            return _run_provision_cmd(cmd, dimensions, test_specs,
                                      suite_id)
        else:
            return _run_swarming_cmd(cmd, dimensions, test_specs,
                                     temp_json_path, suite_id)


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


def _wait_for_results(suite_handler, dry_run=False):
    """Wait for child tasks to finish and return their results.

    @param suite_handler: a cros_suite.SuiteHandler object.
    """
    timeout_util = autotest.chromite_load('timeout_util')
    with timeout_util.Timeout(suite_handler.timeout_mins * 60):
        while True:
            json_output = _fetch_child_tasks(suite_handler.suite_id)
            suite_handler.handle_results(json_output['items'])
            for t in suite_handler.retried_tasks:
                _retry_test(suite_handler, t['task_id'], dry_run=dry_run)

            if suite_handler.is_finished_waiting():
                break

            time.sleep(30)

    logging.info('Finished to wait for child tasks.')


def _retry_test(suite_handler, task_id, dry_run=False):
    """Retry test for a suite.

    We will execute the following actions for retrying a test:
        1. Schedule the test.
        2. Add the test with the new swarming task id to the suite's
           retry handler, but reduce its remaining retries by 1.
        3. Reduce the suite-level max retries by 1.
        4. Remove prevous failed test from retry handler since it's not
           actively monitored by the suite.

    @param suite_handler: a cros_suite.SuiteHandler object.
    @param task_id: The swarming task id for the retried test.
    @param dry_run: Whether to retry a dry run of the test.
    """
    last_retry_specs = suite_handler.get_test_by_task_id(task_id)
    logging.info('Retrying test %s, remaining %d retries.',
                 last_retry_specs.test_specs.test.name,
                 last_retry_specs.remaining_retries - 1)
    retried_task_id = _schedule_test(
            last_retry_specs.test_specs,
            suite_handler.is_provision(),
            suite_id=suite_handler.suite_id,
            dry_run=dry_run)
    previous_retried_ids = last_retry_specs.previous_retried_ids + [task_id]
    suite_handler.add_test_by_task_id(
            retried_task_id,
            cros_suite.TestHandlerSpecs(
                    test_specs=last_retry_specs.test_specs,
                    remaining_retries=last_retry_specs.remaining_retries - 1,
                    previous_retried_ids=previous_retried_ids))
    suite_handler.set_max_retries(suite_handler.max_retries - 1)
    suite_handler.remove_test_by_task_id(task_id)
