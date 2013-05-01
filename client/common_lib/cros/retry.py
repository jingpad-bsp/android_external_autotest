# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, random, signal, sys, time

from autotest_lib.client.common_lib import error
from autotest_lib.frontend.afe.json_rpc import proxy


class TimeoutException(Exception):
    """
    Exception to be raised for when alarm is triggered.
    """
    pass


def handler(signum, frame):
    """
    Register a handler for the timeout.
    """
    raise TimeoutException('Call is timed out.')


def timeout(func, args=(), kwargs={}, timeout_sec=60.0, default_result=None):
    """
    This function run the given function using the args, kwargs and
    return the given default value if the timeout_sec is exceeded.

    @param func: function to be called.
    @param args: arguments for function to be called.
    @param kwargs: keyword arguments for function to be called.
    @param timeout_sec: timeout setting for call to exit, in seconds.
    @param default_result: default return value for the function call.

    @return 1: is_timeout 2: result of the function call. If
            is_timeout is True, the call is timed out. If the
            value is False, the call is finished on time.
    """
    old_handler = signal.signal(signal.SIGALRM, handler)

    timeout_sec_n = int(timeout_sec)
    # In case the timeout is rounded to 0, force to set it to default value.
    if timeout_sec_n == 0:
        timeout_sec_n = 60
    try:
        old_alarm_sec = signal.alarm(timeout_sec_n)
        if old_alarm_sec > 0:
            old_timeout_time = time.time() + old_alarm_sec
        default_result = func(*args, **kwargs)
        return False, default_result
    except TimeoutException:
        return True, default_result
    finally:
        # Cancel the timer if the function returned before timeout or
        # exception being thrown.
        signal.alarm(0)
        # Restore previous Signal handler and alarm
        if old_handler:
            signal.signal(signal.SIGALRM, old_handler)
        if old_alarm_sec > 0:
            old_alarm_sec = int(old_timeout_time - time.time())
            if old_alarm_sec <= 0:
                old_alarm_sec = 1;
            signal.alarm(old_alarm_sec)


def retry(ExceptionToCheck, timeout_min=1.0, delay_sec=3, blacklist=None):
    """Retry calling the decorated function using a delay with jitter.

    Will raise RPC ValidationError exceptions from the decorated
    function without retrying; a malformed RPC isn't going to
    magically become good. Will raise exceptions in blacklist as well.

    original from:
      http://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/

    @param ExceptionToCheck: the exception to check.  May be a tuple of
                             exceptions to check.
    @param timeout_min: timeout in minutes until giving up.
    @param delay_sec: pre-jittered delay between retries in seconds.  Actual
                      delays will be centered around this value, ranging up to
                      50% off this midpoint.
    @param blacklist: a list of exceptions that will be raised without retrying
    """
    def deco_retry(func):
        random.seed()


        def delay():
            """
            'Jitter' the delay, up to 50% in either direction.
            """
            random_delay = random.uniform(.5 * delay_sec, 1.5 * delay_sec)
            logging.warning('Retrying in %f seconds...', random_delay)
            time.sleep(random_delay)


        def func_retry(*args, **kwargs):
            deadline = time.time() + timeout_min * 60  # convert to seconds.
            # Used to cache exception to be raised later.
            exc_info = None
            delayed_enabled = False
            exception_tuple = () if blacklist is None else tuple(blacklist)
            while time.time() < deadline:
                if delayed_enabled:
                    delay()
                else:
                    delayed_enabled = True
                try:
                    # Clear the cache
                    exc_info = None
                    is_timeout, result = timeout(func, args, kwargs,
                                                 timeout_min*60)
                    if not is_timeout:
                        return result
                except exception_tuple:
                    raise
                except (error.CrosDynamicSuiteException,
                        proxy.ValidationError):
                    raise
                except ExceptionToCheck as e:
                    logging.warning('%s(%s)', e.__class__, e)
                    # Cache the exception to be raised later.
                    exc_info = sys.exc_info()
            # The call must have timed out or raised ExceptionToCheck.
            if not exc_info:
                raise TimeoutException('Call is timed out.')
            # Raise the cached exception with original backtrace.
            raise exc_info[0], exc_info[1], exc_info[2]


        return func_retry  # true decorator
    return deco_retry
