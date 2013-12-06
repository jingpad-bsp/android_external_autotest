#!/usr/bin/env python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import functools
import traceback

def dbus_method_wrapper(ok_logger, error_logger, *args, **kwargs):
    """
    Factory method for decorator to declare dbus service methods.

    This decorator is an improvement over dbus.service.method
    It logs the response / Exceptions raised in the function call, but otherwise
    behaves identical to a function decorated with dbus.service.method

    To declare a function DoStuff:
    #  @utils.dbus_method_wrapper(logging.info, logging.warning, interface, ...)
    #  DoStuff(...):
    #    pass

    @param ok_logger: A function that accepts a string argument to log the
            response from the decorated function.

    @param error_logger: A function accepts a string argument to log the
            exception raised by the decorated function.

    Extra arguments required are those required by the dbus.service.method
    decorator factory.
    """
    dbus_decorator = dbus.service.method(*args, **kwargs)
    def wrapper(func):
        """
        The decorator returned by this factory.

        @param func: The function to be decorated.

        """
        dbus_func = dbus_decorator(func)
        @functools.wraps(func)
        def wrapped_func(*args, **kwargs):
            """The modified function for the decorated function."""
            try:
                retval = dbus_func(*args, **kwargs)
                ok_logger('Response OK: |%s|' % repr(retval))
            except Exception as e:
                error_logger('Response ERROR: |%s|' % repr(e))
                error_logger(traceback.format_exc())
                raise
            return retval
        return wrapped_func
    return wrapper
