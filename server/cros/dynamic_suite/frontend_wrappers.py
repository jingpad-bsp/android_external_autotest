# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, random, time
import common
from autotest_lib.client.common_lib.cros import retry
from autotest_lib.server import frontend
from autotest_lib.frontend.afe.json_rpc import proxy


class RetryingAFE(frontend.AFE):
    """Wrapper around frontend.AFE that retries all RPCs.

    Timeout for retries and delay between retries are configurable.
    """
    def __init__(self, timeout_min, delay_sec, **dargs):
        """Constructor

        @param timeout_min: timeout in minutes until giving up.
        @param delay_sec: pre-jittered delay between retries in seconds.
        """
        self.timeout_min = timeout_min
        self.delay_sec = delay_sec
        super(RetryingAFE, self).__init__(**dargs)

    @retry.retry(Exception, timeout_min=30, delay_sec=10,
                 blacklist=[ImportError])
    def run(self, call, **dargs):
        return super(RetryingAFE, self).run(call, **dargs)


class RetryingTKO(frontend.TKO):
    """Wrapper around frontend.TKO that retries all RPCs.

    Timeout for retries and delay between retries are configurable.
    """
    def __init__(self, timeout_min, delay_sec, **dargs):
        """Constructor

        @param timeout_min: timeout in minutes until giving up.
        @param delay_sec: pre-jittered delay between retries in seconds.
        """
        self.timeout_min = timeout_min
        self.delay_sec = delay_sec
        super(RetryingTKO, self).__init__(**dargs)


    @retry.retry(Exception, timeout_min=30, delay_sec=10,
                 blacklist=[ImportError])
    def run(self, call, **dargs):
        return super(RetryingTKO, self).run(call, **dargs)
