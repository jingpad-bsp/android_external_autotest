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
TASK_FINISHED_STATUS = ['COMPLETED', 'EXPIRED', 'CANCELED', 'TIMED_OUT']


def _get_client():
    return os.path.join(
            os.path.expanduser('~'),
            'chromiumos/chromite/third_party/swarming.client/swarming.py')


def get_basic_swarming_cmd(command):
    return [_get_client(), command,
            '--auth-service-account-json', SERVICE_ACCOUNT,
            '--swarming', SWARMING_SERVER]
