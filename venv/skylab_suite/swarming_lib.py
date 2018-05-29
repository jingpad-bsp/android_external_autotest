# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module for swarming execution."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os


SERVICE_ACCOUNT = '/creds/skylab_swarming_bot/skylab_bot_service_account.json'
SWARMING_SERVER = 'chrome-swarming.appspot.com'
TASK_COMPLETED = 'COMPLETED'
TASK_COMPLETED_SUCCESS = 'COMPLETED (SUCCESS)'
TASK_COMPLETED_FAILURE = 'COMPLETED (FAILURE)'
TASK_EXPIRED = 'EXPIRED'
TASK_CANCELED = 'CANCELED'
TASK_TIMEDOUT = 'TIMED_OUT'
TASK_FINISHED_STATUS = [TASK_COMPLETED,
                        TASK_EXPIRED,
                        TASK_CANCELED,
                        TASK_TIMEDOUT]
TASK_FAILED_STATUS = [TASK_EXPIRED,
                      TASK_CANCELED,
                      TASK_TIMEDOUT]


def _get_client():
    return os.path.join(
            os.path.expanduser('~'),
            'chromiumos/chromite/third_party/swarming.client/swarming.py')


def get_basic_swarming_cmd(command):
    return [_get_client(), command,
            '--auth-service-account-json', SERVICE_ACCOUNT,
            '--swarming', SWARMING_SERVER]


def get_task_link(task_id):
    return 'https://%s/user/task/%s' % (SWARMING_SERVER, task_id)


def get_task_final_state(task):
    """Get the final state of a swarming task.

    @param task: the json output of a swarming task fetched by API tasks.list.
    """
    state = task['state']
    if state == TASK_COMPLETED:
        state = (TASK_COMPLETED_FAILURE if task['failure'] else
                 TASK_COMPLETED_SUCCESS)

    return state
