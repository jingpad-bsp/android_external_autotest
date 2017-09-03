# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Safe signal handling library.

Safe signal handling is hard.  This module provides some tools to make
it a little easier.

Nothing in this module is thread safe.

For reference, see signal(7) and
https://docs.python.org/2/library/signal.html

Python and signals:

Python does not provide default signal handlers for SIGTERM or SIGHUP.
This means that if you send SIGTERM to a Python process, it won't run
any finally suites, __exit__() methods, or atexit functions!

In general, anything process specific does not need to be cleaned up if
the process is exiting.  This includes file descriptors (open files) and
allocated memory.

Anything external to the process needs to be cleaned up.  This includes
lock files and IO transactions (storage or network).

Subprocesses may or may not need to be cleaned up.  The orphaned
subprocesses will be adopted and reaped by PID 1 or a subreaper.
However, the signal, e.g. SIGTERM, will not be sent to subprocesses
unless explicitly set to do so.

It is possible to receive another signal while handling a signal.  After
a signal handler returns, control returns to where the signal was
received.  In other words, signal handler calls go onto a "stack",
although signal handlers cannot return values.

A exception raised by a signal handler that escapes the signal handler
call will be raised where the signal was received.

It is possible to receive a signal while handling an exception,
including an exception raised while handling a signal.

If multiple signals are received at once and their handlers all raise
exceptions, you can probably expect Python to exit without running any
finally suites, __exit__() methods, or atexit functions.

It is possible to set signal handlers inside a signal handler.  Please
do not do that.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging
import signal

import contextlib2

logger = logging.getLogger(__name__)


class handle_signals(object):
    """Context manager chaining multiple SignalHandlerContext.

    This is single use.
    """

    def __init__(self, signums, handler):
        self._handler = handler
        self._signums = signums
        self._stack = contextlib2.ExitStack()

    def __enter__(self):
        stack = self._stack.__enter__()
        for signum in self._signums:
            stack.enter_context(handle_signal(signum, self._handler))

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self._stack.__exit__(exc_type, exc_val, exc_tb)


class handle_signal(object):
    """Signal handler context.

    This context manager sets a signal handler during the execution of
    the suite and restores the original signal handler when exiting.

    See signal.signal() for values of signum and handler.

    This is reusable and reentrant.
    """

    def __init__(self, signum, handler):
        self._handler = handler
        self._signum = signum
        self._old_handlers = []

    def __enter__(self):
        old = signal.signal(self._signum, self._handler)
        self._old_handlers.append(old)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        old = self._old_handlers.pop()
        signal.signal(self._signum, old)
        return False
