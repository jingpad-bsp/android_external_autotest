# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, random, time
from autotest_lib.client.common_lib import error
from autotest_lib.frontend.afe.json_rpc import proxy


def retry(ExceptionToCheck, timeout_min=1, delay_sec=3):
    """Retry calling the decorated function using a delay with jitter.

    Will raise RPC ValidationError exceptions from the decorated
    function without retrying; a malformed RPC isn't going to
    magically become good.

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
                try:
                    return func(*args, **kwargs)
                except error.CrosDynamicSuiteException, e:
                    raise e
                except proxy.ValidationError, e:
                    raise e
                except ExceptionToCheck, e:
                    # 'Jitter' the delay, up to 50% in either direction.
                    delay = random.uniform(.5 * delay_sec, 1.5 * delay_sec)
                    logging.warning("%s(%s), Retrying in %f seconds...",
                                    e.__class__, e, delay)
                    time.sleep(delay)
            else:
                # On the last try, run func() and allow exceptions to escape.
                return func(*args, **kwargs)
            return
        return func_retry  # true decorator
    return deco_retry
