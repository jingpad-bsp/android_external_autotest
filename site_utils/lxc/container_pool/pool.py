# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import Queue
import threading
import time

import common
from autotest_lib.site_utils.lxc.container_pool import error
from autotest_lib.site_utils.lxc.container_pool import multi_logger


# The maximum number of concurrent workers.  Each worker is responsible for
# managing the creation of a single container.
# TODO(kenobi): This may be need to be adjusted for different hosts (e.g. full
# vs quarter shards)
_MAX_CONCURRENT_WORKERS = 5
# Timeout (in seconds) for container creation.  After this amount of time,
# container creation tasks are abandoned and retried.
_CONTAINER_CREATION_TIMEOUT = 600
# The period (in seconds) affects the rate at which the monitor thread runs its
# event loop.  This drives a number of other factors, e.g. how long to wait for
# the thread to respond to shutdown requests.
_MIN_MONITOR_PERIOD = 0.1
# The default size of the container pool.
_DEFAULT_POOL_SIZE = 20

_logger = multi_logger.create('pool')


class Pool(object):
    """A fixed-size pool of LXC containers.

    Containers are created using a factory that is passed to the Pool.  A pool
    size is passed at construction time - this is the number of containers the
    Pool will attempt to maintain.  Whenever the number of containers falls
    below the given size, the Pool will start creating new containers to
    replenish itself.

    In order to avoid overloading the host, the number of simultaneous container
    creations is limited to _MAX_CONCURRENT_WORKERS.

    When container creation produces errors, those errors are saved (see
    Pool.errors).  It is the client's responsibility to periodically check and
    empty out the error queue.
    """

    def __init__(self, factory, size=_DEFAULT_POOL_SIZE):
        """Creates a new Pool instance.

        @param factory: A factory object that will be called upon to create new
                        containers.  The passed object must have a method called
                        "create_container" that takes no arguments and returns
                        an instance of a Container.
        @param size: The size of the Pool.  The Pool attempts to keep this many
                     containers running at all times.
        """
        # Pools of size less than 2 don't make sense.  Don't allow them.
        if size < 2:
            raise ValueError('Invalid pool size.')

        _logger.debug('Pool.__init__ called.  Size: %d', size)
        self._pool = Queue.Queue(size)
        self._monitor = _Monitor(factory, self._pool)
        self._monitor.start()


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
            # Block only if timeout is not zero.
            _logger.info('Pool.get called.')
            return self._pool.get(block=(timeout != 0),
                                  timeout=timeout)
        except Queue.Empty:
            return None


    def cleanup(self, timeout=0):
        """Cleans up the container pool.

        Stops all worker threads, and destroys all Containers still in the Pool.

        @param timeout: For testing.  If this is non-zero, it specifies the
                        number of seconds to wait for each worker to shut down.
                        An error is raised if shutdown has not occurred by then.
                        If zero (the default), don't wait for worker threads to
                        shut down, just return immediately.
        """
        _logger.info('Pool.cleanup called.')
        # Stop the monitor thread, then drain the pool.
        self._monitor.stop(timeout)

        try:
            dcount = 0
            _logger.debug('Emptying container pool')
            while True:
                container = self._pool.get(block=False)
                dcount += 1
                container.destroy()
        except Queue.Empty:
            pass
        finally:
            _logger.debug('Done.  Destroyed %d containers', dcount)


    @property
    def errors(self):
        """Returns worker errors.

        @return: A Queue containing all the errors encountered on worker
                 threads.
        """
        return self._monitor.errors;


class _Monitor(threading.Thread):
    """A thread that manages the creation of containers for the pool.

    Container creation is potentially time-consuming and can hang or crash.  The
    Monitor class manages a pool of independent threads, each responsible for
    the creation of a single Container.  This provides parallelized container
    creation and ensures that a single Container creation hanging/crashing does
    not starve or crash the Pool.
    """

    def __init__(self, factory, pool):
        """Creates a new monitor.

        @param factory: A container factory.
        @param pool: A pool instance to push created containers into.
        """
        super(_Monitor, self).__init__(name='pool_monitor')

        self._factory = factory
        self._pool = pool

        # List of worker threads.  Access this only from the monitor thread.
        self._workers = []

        # A flag for stopping the monitor.
        self._stop = False

        # Stores errors from worker threads.
        self.errors = Queue.Queue()


    def run(self):
        """Supplies the container pool with containers."""
        _logger.debug('Start event loop.')
        while not self._stop:
            self._create_workers()
            self._poll_workers()
            time.sleep(_MIN_MONITOR_PERIOD)
        _logger.debug('Exit event loop.')

        # Clean up - stop all workers.
        for worker in self._workers:
            worker.cancel()


    def stop(self, timeout=0):
        """Stops this thread.

        This function blocks until the monitor thread has stopped.

        @param timeout: If this is a non-zero number, wait this long (in
                        seconds) for each worker thread to stop.  If zero (the
                        default), don't wait for worker threads to exit.

        @raise WorkerTimeoutError: If a worker thread does not exit within the
                                   specified timeout.
        """
        _logger.info('Stop requested.')
        self._stop = True
        self.join()
        _logger.info('Stopped.')
        # Wait for workers if timeout was requested.
        if timeout > 0:
            _logger.debug('Waiting for workers to terminate...')
            for worker in self._workers:
                worker.join(timeout)
                if worker.is_alive():
                    raise error.WorkerTimeoutError()


    def _create_workers(self):
        """Spawns workers to handle container requests.

        This method modifies the _workers list and should only be called from
        within run().
        """
        if self._pool.full():
            return

        # Create workers to refill the pool.
        qsize = self._pool.qsize()
        shortfall = self._pool.maxsize - qsize
        old_worker_count = len(self._workers)

        # Avoid spamming - only log if the monitor is taking some action.  Log
        # this before creating worker threads, because we are counting live
        # threads and want to avoid race conditions w.r.t. threads actually
        # starting.
        if old_worker_count != shortfall:
            new_workers = shortfall - old_worker_count
            # This can include workers that aren't currently in the self._worker
            # list, e.g. workers that were dropped from the list because they
            # timed out.
            active_workers = sum([1 for t in threading.enumerate()
                                  if type(t) is _Worker])
            # qsize    : Current size of the container pool.
            # shortfall: Number of empty slots currently in the pool.
            # workers  : m+n, where m is the current number of active worker
            #            threads and n is the number of new threads created.
            _logger.debug('qsize:%d shortfall:%d workers:%d+%d',
                          qsize, shortfall, active_workers, new_workers)

        while len(self._workers) < shortfall:
            worker = _Worker(self._factory,
                             self._on_worker_result,
                             self._on_worker_error)
            worker.start()
            self._workers.append(worker)


    def _poll_workers(self):
        """Checks worker states and deals with them.

        This method modifies the _workers list and should only be called from
        within run().

        Completed workers are taken off the worker list and their results/errors
        are logged.
        """
        completed = []
        incomplete = []
        for worker in self._workers:
            if worker.check_health():
                incomplete.append(worker)
            else:
                completed.append(worker)

        self._workers = incomplete


    def _on_worker_result(self, result):
        """Receives results from completed worker threads.

        Pass this as the result callback for worker threads.  Worker threads
        should call this when they produce a container.
        """
        _logger.debug('Worker result: %r' % result)
        self._pool.put(result)


    def _on_worker_error(self, err):
        """Receives errors from worker threads.

        Pass this as the error callback for worker threads.  Worker threads
        should call this if errors occur.
        """
        self.errors.put(err)
        _logger.error('Worker error: %s', err)


class _Worker(threading.Thread):
    """A worker thread tasked with managing the creation of a single container.

    The worker is a daemon thread that calls upon a container factory to create
    a single container.  If container creation raises any exceptions, they are
    logged and the worker exits.  The worker also provides a mechanism for the
    parent thread to impose timeouts on container creation.
    """

    # Throttles the number of concurrent running workers.  Workers attempt to
    # acquire the semaphore at the start of their run() method.  Throttled
    # workers are thus alive, but waiting.  Workers release the semaphore when
    # they are done running, or when they are cancelled.
    _throttle = threading.BoundedSemaphore(value=_MAX_CONCURRENT_WORKERS)


    def __init__(self, factory, result_cb, error_cb):
        """Creates a new Worker.

        @param factory: A factory object that will be called upon to create
                        Containers.
        """
        super(_Worker, self).__init__(name='pool_worker')
        # Hanging worker threads should not keep the pool process alive.
        self.daemon = True

        self._factory = factory

        self._result_cb = result_cb
        self._error_cb = error_cb

        self._cancelled = False
        self._start_time = None

        # A lock for breaking race conditions in worker cancellation.
        self._completion_lock = threading.Lock()
        self._completed = False


    def run(self):
        """Creates a single container."""
        self._throttle.acquire()
        self._start_time = time.time()
        container = None
        try:
            container = self._factory.create_container()
        except Exception as e:
            _logger.error('Error: %s', e)
            self._error_cb(e)
        finally:
            # All this has to happen atomically, otherwise race conditions can
            # arise w.r.t. cancellation.
            with self._completion_lock:
                self._completed = True
                if self._cancelled:
                    # If the job was cancelled, destroy the container instead of
                    # putting it in the result queue.  Do not release the
                    # throttle, as it would have been released when the
                    # cancellation occurred.
                    if container is not None:
                        container.destroy()
                else:
                    # Put the container in the result field.  Release the
                    # throttle so another task can be picked up.
                    # Container may be None if errors occurred.
                    if container is not None:
                        self._result_cb(container)
                    self._throttle.release()


    def cancel(self):
        """Cancels the work request.

        The container will be destroyed when created, instead of being added to
        the container pool.
        """
        with self._completion_lock:
            if self._completed:
                return False
            else:
                self._cancelled = True
                self._throttle.release()
                return True


    def check_health(self):
        """Checks that a worker is alive and has not timed out.

        Checks the run time of the worker to make sure it hasn't timed out.
        Cancels workers that exceed the timeout.

        @return: True if the worker is alive and has not timed out, False
                 otherwise.
        """
        if not self.is_alive() or self._cancelled:
            return False

        # If alive, check the timeout and cancel if necessary.  Check for
        # _start_time being None because it is not actually set until the thread
        # acquires a grant from the throttle.
        if (self._start_time is not None and
                time.time() - self._start_time > _CONTAINER_CREATION_TIMEOUT):
            if self.cancel():
                self._error_cb(error.WorkerTimeoutError())
            return False

        return True
