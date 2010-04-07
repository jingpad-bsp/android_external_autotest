# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time
from autotest_lib.client.common_lib import error


class TimeoutError(error.TestError):
    """Error raised when we time out when waiting on a condition."""


def poll_for_condition(
    condition, exception=None, timeout=10, sleep_interval=0.1, desc=None):
    """Poll until a condition becomes true.

    condition: function taking no args and returning bool
    exception: exception to throw if condition doesn't become true
    timeout: maximum number of seconds to wait
    sleep_interval: time to sleep between polls
    desc: description of default TimeoutError used if 'exception' is None

    Raises:
        'exception' arg if supplied; site_utils.TimeoutError otherwise
    """
    start_time = time.time()
    while True:
        if condition():
            return
        if time.time() + sleep_interval - start_time > timeout:
            if exception:
                raise exception

            if desc:
                desc = 'Timed out waiting for condition: %s' % desc
            else:
                desc = 'Timed out waiting for unnamed condition'
            raise error.TestError(desc)

        time.sleep(sleep_interval)
