# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from skylab_suite import swarming_lib


def test_form_requests():
    """Test raw requests for swarming API."""
    task_name = 'provision_task'
    parent_task_id = 'fake_parent_task_id'
    priority = 70
    tags = ['parent_task_id:fake_id']
    tags.append('task_name:%s' % task_name)
    user = 'skylab_suite'
    fallback_dimensions = {'pool': 'ChromeOSSkylab'}
    normal_dimensions = fallback_dimensions.copy()
    normal_dimensions['provisionable-cros-version'] = (
            'lumpy-release/R65-10323.58.0')
    cmds = [['python', '-c', 'print("first")'],
            ['python', '-c', 'print("second")']]
    dimensions = [normal_dimensions, fallback_dimensions]
    expiration_secs = swarming_lib.DEFAULT_EXPIRATION_SECS
    timeout_secs = swarming_lib.DEFAULT_TIMEOUT_SECS
    slice_expiration_secs = [expiration_secs, expiration_secs]

    source_request = {
            'name': task_name,
            'parent_task_id': parent_task_id,
            'priority': priority,
            'tags': tags,
            'user': user,
            'task_slices': [
                    {'expiration_secs': expiration_secs,
                     'properties': {
                            'command': cmds[0],
                            'dimensions': [
                                    {'key': 'pool',
                                     'value': 'ChromeOSSkylab'},
                                    {'key': 'provisionable-cros-version',
                                     'value': 'lumpy-release/R65-10323.58.0'},
                            ],
                            'grace_period_secs': timeout_secs,
                            'execution_timeout_secs': timeout_secs,
                            'io_timeout_secs': timeout_secs,
                     }},
                    {'expiration_secs': expiration_secs,
                     'properties': {
                             'command': cmds[1],
                             'dimensions': [
                                    {'key': 'pool',
                                     'value': 'ChromeOSSkylab'},
                             ],
                             'grace_period_secs': timeout_secs,
                             'execution_timeout_secs': timeout_secs,
                             'io_timeout_secs': timeout_secs,
                     }},
            ],
    }

    json_request = swarming_lib.make_fallback_request_dict(
            cmds, dimensions, slice_expiration_secs, task_name, priority,
            tags, user, parent_task_id=parent_task_id)
    assert json_request == source_request
