# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import Queue
import collections
import threading

import common
from autotest_lib.site_utils.lxc.container_pool import multi_logger


_logger = multi_logger.create('pool')


class Pool(object):
    """A fixed-size pool of LXC containers.

    Containers are created using a factory instance that is passed to the Pool.
    The Pool utilizes a worker thread to instantiate Container instances in the
    background.

    The worker thread logs errors thrown by the factory and attempts to
    continue.  Only the last 10 errors seen are kept.
    """

    def __init__(self, factory, size=5):
        """Creates a new Pool instance.

        @param factory: A factory object that will be called upon to create new
                        containers.  The passed object must have a method called
                        "create_container" that takes no arguments and returns
                        an instance of a Container.
        @param size: The maximum size of the Pool.  The worker thread attempts
                     to keep this many Container instances in the Pool at all
                     times.
        """
        # Pools of size less than 2 don't make sense.  Don't allow them.
        if size < 2:
            raise ValueError('Invalid pool size.')

        # At any given time, the worker thread is holding on to one item and
        # waiting to add it to the pool.  So to get an effective max pool size
        # of n, the waiting queue is actually of size (n-1).
        self._pool = Queue.Queue(size-1)
        self._worker = _FactoryWorker(factory, self._pool)
        self._worker.start()


    def get(self, timeout=0):
        """Gets a container from the pool.

        @param timeout: Number of seconds to wait before returning.
                        - If 0 (the default), return immediately.  If a
                          Container is not immediately available, return None.
                        - If a positive number, block at most <timeout> seconds,
                          then return None if a Container was not available
                          within that time.
                        - If None, block indefinitely until a Container is
                          available.

        @return: A container from the pool.
        """
        try:
            # Block only if timout is not zero.
            return self._pool.get(block=(timeout != 0),
                                  timeout=timeout)
        except Queue.Empty:
            return None


    def cleanup(self, pedantic=False):
        """Cleans up the container pool.

        Stops the worker thread, and destroys all Containers still in the Pool.

        @param pedantic: If set to True, this function will raise an error if
                         the worker thread does not shut down cleanly.  False by
                         default.
        """
        # Stop the factory thread, then drain the pool.
        self._worker.stop()
        try:
            _logger.debug('Emptying container pool')
            while True:
                # Allow a timeout so the factory thread has a chance to exit.
                # This ensures all containers are cleaned up.
                container = self._pool.get(timeout=0.1)
                container.destroy()
        except Queue.Empty:
            pass
        if pedantic:
            # Ensure the worker thread shuts down.  Raise an error if this does
            # not happen within 1 second.
            _logger.debug('Waiting for worker thread to exit...')
            self._worker.join(1)
            if self._worker.is_alive():
                raise threading.ThreadError('FactoryWorker failed to stop.')


    @property
    def errors(self):
        """The last 10 errors the worker thread encountered.

        @return: A list containing up to 10 errors.
        """
        return self._worker.errors;


class _FactoryWorker(threading.Thread):
    """A thread whose task it is to keep the pool filled."""

    def __init__(self, factory, pool):
        """Creates a new worker thread.

        @param factory: A container factory.
        @param pool: A pool instance to push created containers into.
        """
        self._factory = factory
        self._pool = pool
        self._stop = False
        self._errors_lock = threading.Lock()
        self._errors = collections.deque(maxlen=10)
        super(_FactoryWorker, self).__init__(name='pool_worker')


    def run(self):
        """Supplies the container pool with containers."""
        # Just continuously create containers and push them into the pool.
        # TODO(kenobi): This is too simplistic.  If the factory hangs, it will
        # hang the entire worker thread, which will starve the pool (and also
        # prevent it from shutting down).  This placeholder code is just here
        # for now to get an initial prototype up and running.
        _logger.debug('Start event loop.')
        while not self._stop:
            try:
                container = self._factory.create_container()
                self._pool.put(container)
                _logger.debug('Pool size: %d', self._pool.qsize())
            except Exception as e:
                # Log errors, try again.
                with self._errors_lock:
                    self._errors.append(e)
        _logger.debug('Exit event loop.')


    def stop(self):
        """Stops this thread."""
        _logger.debug('Stop requested.')
        self._stop = True


    @property
    def errors(self):
        """The last 10 errors that this thread encountered.

        @return: A list containing up to 10 errors.
        """
        with self._errors_lock:
            return list(self._errors)
