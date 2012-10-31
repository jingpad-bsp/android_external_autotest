# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import sys
import threading
import time


class BaseStressor(threading.Thread):
    """
    Implements common functionality for *Stressor classes.

    @var stressor: callable which performs a single stress event.
    """
    def __init__(self, stressor, escalate_exceptions=True):
        """
        Initialize the ControlledStressor.

        @param stressor: callable which performs a single stress event.
        @param escalate_exceptions: whether to escalate exceptions to the parent
            thread; defaults to True.
        """
        super(BaseStressor, self).__init__()
        self.daemon = True
        self.stressor = stressor
        self._escalate_exceptions = escalate_exceptions
        self._exc_info = None


    def start(self, start_condition=None):
        """
        Creates a new thread which will call the run() method.

        Optionally takes a wait condition before the stressor loop. Returns
        immediately.

        @param start_condition: the new thread will wait until this optional
            callable returns True before running the stressor.
        """
        self._start_condition = start_condition
        super(BaseStressor, self).start()


    def run(self):
        """
        Introduce a delay then start the stressor loop.

        Overloaded from threading.Thread. This is run in a separate thread when
        start() is called.
        """
        if self._start_condition:
            while not self._start_condition():
                time.sleep(1)
        try:
            self._loop_stressor()
        except Exception as e:
            if self._escalate_exceptions:
                self._exc_info = sys.exc_info()
            raise


    def _loop_stressor(self):
        """
        Apply stressor in a loop.

        Overloaded by the particular *Stressor.
        """
        raise NotImplementedError


    def reraise(self):
        """
        Reraise an exception raised in the thread's stress loop.

        This is a No-op if no exception was raised.
        """
        if self._exc_info:
            exc_info = self._exc_info
            self._exc_info = None
            raise exc_info[0], exc_info[1], exc_info[2]


class ControlledStressor(BaseStressor):
    """
    Run a stressor in loop on a separate thread.

    Creates a new thread and calls |stressor| in a loop until stop() is called.
    """
    def __init__(self, stressor, escalate_exceptions=True):
        """
        Initialize the ControlledStressor.

        @param stressor: callable which performs a single stress event.
        @param escalate_exceptions: whether to escalate exceptions to the parent
            thread; defaults to True.
        """
        self._complete = threading.Event()
        super(ControlledStressor, self).__init__(stressor, escalate_exceptions)


    def _loop_stressor(self):
        """Overloaded from parent."""
        iteration_num = 0
        while not self._complete.is_set():
            iteration_num += 1
            logging.info('Stressor iteration: %d' % iteration_num)
            self.stressor()


    def start(self, start_condition=None):
        """Start applying the stressor.

        Overloaded from parent.

        @param start_condition: the new thread will wait to until this optional
            callable returns True before running the stressor.
        """
        self._complete.clear()
        super(ControlledStressor, self).start(start_condition)


    def stop(self, timeout=45):
        """
        Stop applying the stressor.

        @param timeout: maximum time to wait for a single run of the stressor to
            complete, defaults to 45 seconds.
        """
        self._complete.set()
        self.join(timeout)
        self.reraise()


class CountedStressor(BaseStressor):
    """
    Run a stressor in a loop on a separate thread a given number of times.

    Creates a new thread and calls |stressor| in a loop |iterations| times. The
    calling thread can use wait() to block until the loop completes.
    """
    def _loop_stressor(self):
        """Overloaded from parent."""
        for iteration_num in xrange(1, self._iterations + 1):
            logging.info('Stressor iteration: %d of %d' % (iteration_num,
                                                           self._iterations))
            self.stressor()


    def start(self, iterations, start_condition=None):
        """
        Apply the stressor a given number of times.

        Overloaded from parent.

        @param iterations: number of times to apply the stressor.
        @param start_condition: the new thread will wait to until this optional
            callable returns True before running the stressor.
        """
        self._iterations = iterations
        super(CountedStressor, self).start(start_condition)


    def wait(self, timeout=None):
        """Wait until the stressor completes.

        @param timeout: maximum time for the thread to complete, by default
            never times out.
        """
        self.join(timeout)
        self.reraise()
