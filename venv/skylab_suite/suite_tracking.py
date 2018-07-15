# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Functions for tracking & reporting a suite run."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging
import logging.config

from lucifer import autotest
from skylab_suite import swarming_lib



def log_suite_results(suite_name, suite_handler):
    """Log suite and its child tests' results & links.

    @param suite_job: A cros_suite.Suite object.

    @return the return code of suite decided by its child tests' results.
    """
    test_results = _parse_test_results(suite_handler)
    suite_state, return_code = _get_suite_state(test_results, suite_handler)
    if not test_results:
        logging.info(('Suite %s timed out in waiting, test results '
                      'are not parsed because they may still run.'), suite_name)
        return return_code

    logging.info('################# SUITE REPORTING #################')
    logging.info('Suite Job %s %s', suite_name, suite_state)
    _log_test_results(test_results)

    logging.info('Links to tests:')
    logging.info('Suite Job %s %s', suite_name,
                 swarming_lib.get_task_link(suite_handler.suite_id))
    _log_test_links(test_results)

    _log_buildbot_links(suite_handler, suite_name, test_results)

    return return_code


def _log_buildbot_links(suite_handler, suite_name, test_results):
    logging.info('Links for buildbot:')
    annotations = autotest.chromite_load('buildbot_annotations')
    reporting_utils = autotest.load('server.cros.dynamic_suite.reporting_utils')
    print(annotations.StepLink(
            'Link to suite: %s' % suite_name,
            swarming_lib.get_task_link(suite_handler.suite_id)))

    if (suite_handler.is_provision() and
        suite_handler.is_provision_successfully_finished()):
        # There could be some child tasks may still run after provision suite
        # finishes and claims that it succeeds. Skip logging them in buildbot.
        return

    for result in test_results:
        if result['state'] not in [swarming_lib.TASK_COMPLETED_SUCCESS,
                                   swarming_lib.TASK_RUNNING]:
            anchor_test = result['test_name']
            if suite_handler.is_provision():
                anchor_test += '-' + result['dut_name']

            show_text = '[{prefix}]: {anchor}'.format(
                    prefix='Test-logs',
                    anchor=anchor_test)
            print(annotations.StepLink(
                    show_text,
                    swarming_lib.get_task_link(result['task_ids'][0])))

            if not suite_handler.is_provision():
                print(annotations.StepLink(
                        '[Test-History]: %s' % result['test_name'],
                        reporting_utils.link_test_history(result['test_name'])))


def _log_test_results(test_results):
    """Log child results for a suite."""
    logging.info('Start outputing test results:')
    name_column_width = max(len(result['test_name']) for result in
                            test_results) + 3
    for result in test_results:
        padded_name = result['test_name'].ljust(name_column_width)
        logging.info('%s%s', padded_name, result['state'])
        if result['retry_count'] > 0:
            logging.info('%s  retry_count: %s', padded_name,
                         result['retry_count'])


def _parse_test_results(suite_handler):
    """Parse test results after the suite job is finished.

    @param suite_handler: A cros_suite.SuiteHandler object.

    @return a list of test results.
    """
    test_results = []
    for child_task in suite_handler.active_child_tasks:
        task_id = child_task['task_id']
        logging.info('Parsing task results of %s', task_id)
        test_handler_spec = suite_handler.get_test_by_task_id(task_id)
        name = test_handler_spec.test_spec.test.name
        dut_name = test_handler_spec.test_spec.dut_name
        retry_count = len(test_handler_spec.previous_retried_ids)
        all_task_ids = test_handler_spec.previous_retried_ids + [task_id]
        state = swarming_lib.get_task_final_state(child_task)
        test_results.append({
                'test_name': name,
                'state': state,
                'dut_name': dut_name,
                'retry_count': retry_count,
                'task_ids': all_task_ids})

    return test_results


def _get_final_suite_states():
    run_suite_common = autotest.load('site_utils.run_suite_common')
    return {
            swarming_lib.TASK_COMPLETED_FAILURE:
            (
                    swarming_lib.TASK_COMPLETED_FAILURE,
                    run_suite_common.RETURN_CODES.ERROR,
            ),
            # Task No_Resource means no available bots to accept the task.
            # Deputy should check whether it's infra failure.
            swarming_lib.TASK_NO_RESOURCE:
            (
                    swarming_lib.TASK_NO_RESOURCE,
                    run_suite_common.RETURN_CODES.INFRA_FAILURE,
            ),
            # Task expired means a task is not triggered, could be caused by
            #   1. No healthy DUTs/bots to run it.
            #   2. Expiration seconds are too low.
            #   3. Suite run is too slow to finish.
            # Deputy should check whether it's infra failure.
            swarming_lib.TASK_EXPIRED:
            (
                    swarming_lib.TASK_EXPIRED,
                    run_suite_common.RETURN_CODES.INFRA_FAILURE,
            ),
            # Task canceled means a task is canceled intentionally. Deputy
            # should check whether it's infra failure.
            swarming_lib.TASK_CANCELED:
            (
                    swarming_lib.TASK_CANCELED,
                    run_suite_common.RETURN_CODES.INFRA_FAILURE,
            ),
            swarming_lib.TASK_TIMEDOUT:
            (
                    swarming_lib.TASK_TIMEDOUT,
                    run_suite_common.RETURN_CODES.SUITE_TIMEOUT,
            ),
            # Task pending means a task is still waiting for picking up, but
            # the suite already hits deadline. So report it as suite TIMEOUT.
            # It could also be an INFRA_FAILURE due to DUTs/bots shortage.
            swarming_lib.TASK_PENDING:
            (
                    swarming_lib.TASK_TIMEDOUT,
                    run_suite_common.RETURN_CODES.SUITE_TIMEOUT,
            ),
    }


def _get_suite_state(child_test_results, suite_handler):
    """Get a suite's final state and return code."""
    run_suite_common = autotest.load('site_utils.run_suite_common')
    if (suite_handler.is_provision() and
        suite_handler.is_provision_successfully_finished()):
        logging.info('Provisioned duts:')
        for dut in list(suite_handler.successfully_provisioned_duts):
            logging.info(dut)
        return (swarming_lib.TASK_COMPLETED_SUCCESS,
                run_suite_common.RETURN_CODES.OK)

    _final_suite_states = _get_final_suite_states()
    for result in child_test_results:
        if result['state'] in _final_suite_states:
            return _final_suite_states[result['state']]

    return (swarming_lib.TASK_COMPLETED_SUCCESS,
            run_suite_common.RETURN_CODES.OK)


def _log_test_links(child_test_results):
    """Output child results for a suite."""
    for result in child_test_results:
        for idx, task_id in enumerate(result['task_ids']):
            retry_suffix = ' (%dth retry)' % idx if idx > 0 else ''
            logging.info('%s  %s', result['test_name'] + retry_suffix,
                         swarming_lib.get_task_link(task_id))


def setup_logging():
    """Setup the logging for skylab suite."""
    logging.config.dictConfig({
        'version': 1,
        'formatters': {
            'default': {'format': '%(asctime)s %(levelname)-5s| %(message)s'},
        },
        'handlers': {
            'screen': {
                'class': 'logging.StreamHandler',
                'formatter': 'default',
            },
        },
        'root': {
            'level': 'INFO',
            'handlers': ['screen'],
        },
        'disable_existing_loggers': False,
    })
