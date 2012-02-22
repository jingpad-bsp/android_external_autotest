# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, random, time
import common
from autotest_lib.client.common_lib import utils
from autotest_lib.server import frontend


def jittered_delay(delay):
    """Return |delay| +/- up to 50%.

    To calculate this, we first determine 50% of the delay, then multiply by
    a random float between 0.0 and 1.0.  This gets us some value between 0 and
    half of the delay.  Then, we flip a coin to decide whether the delta we
    apply to the delay should be positive or negative.  Finally, we add the
    delta to the delay and return it.

    @param delay: the delay to which to add jitter.
    @return: the delay with jitter added in.
    """
    return delay + random.choice([-1, 1]) * random.random() * .5 * delay


def retry(ExceptionToCheck, timeout_min=1, delay_sec=3):
    """Retry calling the decorated function using a delay with jitter.

    original from:
      http://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/

    @param ExceptionToCheck: the exception to check.  May be a tuple of
                             exceptions to check.
    @param timeout_min: timeout in minutes until giving up.
    @param delay_sec: pre-jittered delay between retries in seconds.  Actual
                      delays will be centered around this value, ranging up to
                      50% off this midpoint.
    """
    def deco_retry(func):
        random.seed()
        def func_retry(*args, **kwargs):
            deadline = time.time() + timeout_min * 60  # convert to seconds.
            while time.time() < deadline:
                delay = jittered_delay(delay_sec)
                try:
                    return func(*args, **kwargs)
                    break
                except ExceptionToCheck, e:
                    msg = "%s(%s), Retrying in %f seconds..." % (e.__class__,
                                                                 e,
                                                                 delay)
                    logging.warning(msg)
                    time.sleep(delay)
            else:
                return func(*args, **kwargs)
            return
        return func_retry  # true decorator
    return deco_retry


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

    @retry(Exception, timeout_min=30, delay_sec=10)
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


    @retry(Exception, timeout_min=30, delay_sec=10)
    def run(self, call, **dargs):
        return super(RetryingTKO, self).run(call, **dargs)
