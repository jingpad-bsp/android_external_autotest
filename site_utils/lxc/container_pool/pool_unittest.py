#!/usr/bin/python
# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import Queue
import logging
import threading
import time
import unittest

import common
from autotest_lib.client.common_lib import error
from autotest_lib.site_utils.lxc import unittest_setup
from autotest_lib.site_utils.lxc.container_pool import error as pool_error
from autotest_lib.site_utils.lxc.container_pool import pool


# A timeout (in seconds) for asynchronous operations.  Note the value of
# TEST_TIMEOUT in relation to pool._CONTAINER_CREATION_TIMEOUT is significant -
# if the latter value is unintentionally set to less than TEST_TIMEOUT, then
# tests may start to malfunction due to workers timing out prematurely.  There
# are some instances where it is appropriate to temporarily set the container
# timeout to a value smaller than the test timeout (see
# PoolTests._forceWorkerTimeouts for an example).
TEST_TIMEOUT = 30


class PoolLifecycleTests(unittest.TestCase):
    """Unit tests for Pool lifecycle."""

    def testCreateAndCleanup(self):
        """Verifies creation and cleanup for various sized pools."""
        # 2 is the minimum pool size.  The others are arbitrary numbers for
        # testing.
        for size in [2, 13, 20]:
            factory = TestFactory()
            self._createAndDestroyPool(factory, size)

            # No containers were requested, so the # factory's creation count
            # should be equal to the requested pool size.
            self.assertEquals(size, factory.create_count)

            # Verify that all containers were cleaned up.
            self.assertEquals(size, factory.destroy_count)


    def testInvalidPoolSize(self):
        """Verifies that invalid sized pools cannot be created."""
        # Pool sizes < 2 don't make sense, and aren't allowed.  Test one at
        # least one negative number, and zero as well.
        for size in [-1, 0, 1]:
            with self.assertRaises(ValueError):
                factory = TestFactory()
                pool.Pool(factory, size)


    def testShutdown_hungFactory(self):
        """Verifies that a hung factory does not prevent clean shutdown."""
        factory = TestFactory()
        factory.pause()
        self._createAndDestroyPool(factory, 3, wait=False)


    def _createAndDestroyPool(self, factory, size, wait=True):
        """Creates a container pool, fully populates it, then destroys it.

        @param factory: A ContainerFactory to use for the Pool.
        @param size: The size of the Pool to create.
        @param wait: If true (the default), fail if the pool does not exit
                     cleanly.  Set this to False for tests where a clean
                     shutdown is not expected (e.g. when exercising things like
                     hung worker threads).
        """
        test_pool = pool.Pool(factory, size=size)

        # Wait for the pool to be fully populated.
        if wait:
            factory.wait(size)

        # Clean up the container pool.
        try:
            test_pool.cleanup(timeout=(TEST_TIMEOUT if wait else 0))
        except threading.ThreadError:
            self.fail('Error while cleaning up container pool:\n%s' %
                      error.format_error())


class PoolTests(unittest.TestCase):
    """Unit tests for the Pool class."""

    # Use an explicit pool size for testing.
    POOL_SIZE = 5

    def setUp(self):
        """Starts tests with a fully populated container pool."""
        self.factory = TestFactory()
        self.pool = pool.Pool(self.factory, size=self.POOL_SIZE)
        # Wait for the pool to be fully populated.
        self.factory.wait(self.POOL_SIZE)


    def tearDown(self):
        """Cleans up the test pool."""
        # Resume the factory so all workers get unblocked and can be cleaned up.
        self.factory.resume()
        # Clean up pool.  Raise errors if the pool thread does not exit cleanly.
        self.pool.cleanup(timeout=TEST_TIMEOUT)


    def testRequestContainer(self):
        """Tests requesting a container from the pool."""
        # Retrieve more containers than the pool can hold, to exercise the pool
        # creation.
        self._getAndVerifyContainers(self.POOL_SIZE + 10)


    def testRequestContainer_factoryPaused(self):
        """Tests pool recovery from a temporarily hung container factory."""
        # Simulate the factory hanging.
        self.factory.pause()

        # Get all created containers
        self._getAndVerifyContainers(self.factory.create_count)

        # Getting another container should fail.
        self._verifyNoContainers()

        # Restart the factory, verify that the container pool recovers.
        self.factory.resume()
        self._getAndVerifyContainers(1)


    def testRequestContainer_factoryHung(self):
        """Verifies that the pool continues working when worker threads hang."""
        # Simulate the factory hanging on all but 1 of the workers.
        self.factory.pause(pool._MAX_CONCURRENT_WORKERS - 1)
        # Pool should still be able to service requests
        self._getAndVerifyContainers(self.POOL_SIZE + 10)


    def testRequestContainer_factoryHung_timeout(self):
        """Verifies that container creation times out as expected.

        Simulates a situation where all of the pool's worker threads have hung
        up while creating containers.  Then verifies that the threads time out,
        and the pool recovers.
        """
        # Simulate the factory hanging on all worker threads.  This will exhaust
        # the pool's worker allocation, which should cause container requests to
        # start failing.
        self.factory.pause(pool._MAX_CONCURRENT_WORKERS)

        # Get all created containers
        self._getAndVerifyContainers(self.factory.create_count)

        # Getting another container should fail.
        self._verifyNoContainers()

        self._forceWorkerTimeouts()

        # We should start getting containers again.
        self._getAndVerifyContainers(self.POOL_SIZE + 10)

        # Check for expected timeout errors in the error log.
        error_count = 0
        try:
            while True:
                self.assertEqual(pool_error.WorkerTimeoutError,
                                 type(self.pool.errors.get_nowait()))
                error_count += 1
        except Queue.Empty:
            pass
        self.assertGreater(error_count, 0)


    # TODO (crbug/774534): Fix this flakey test.
    @unittest.skip('Flakey (http://crbug/774534)')
    def testCleanup_timeout(self):
        """Verifies that timed out containers are still destroyed."""
        # Simulate the factory hanging.
        self.factory.pause()

        # Get all created containers.  Destroy them because we are checking
        # destruction counts later.
        original_create_count = self.POOL_SIZE
        for _ in range(original_create_count):
            self.pool.get(timeout=TEST_TIMEOUT).destroy()

        self._forceWorkerTimeouts()

        # Trigger pool cleanup.  Do not wait for clean shutdown, we know this
        # will not happen because we have hung threads.
        self.pool.cleanup(timeout=0)

        # Count the number of timeouts.
        timeout_count = 0
        while True:
            try:
                e = self.pool.errors.get_nowait()
            except Queue.Empty:
                break
            else:
                if type(e) is pool_error.WorkerTimeoutError:
                    timeout_count += 1

        self.factory.resume()

        # Verify the number of containers that were created.
        self.assertEquals(original_create_count + timeout_count,
                          self.factory.create_count)

        # Allow a timeout so the worker threads that were just unpaused above
        # have a chance to complete.
        start_time = time.time()
        while ((time.time() - start_time) < TEST_TIMEOUT and
               self.factory.create_count != self.factory.destroy_count):
            time.sleep(pool._MIN_MONITOR_PERIOD)
        # Assert that all containers were cleaned up.  This validates that
        # the timed-out worker threads actually cleaned up after themselves.
        self.assertEqual(self.factory.create_count, self.factory.destroy_count)


    def testRequestContainer_factoryCrashed(self):
        """Verifies that the pool continues working when worker threads die."""
        # Cause the factory to crash when create is called.
        self.factory.crash_on_create = True

        # Get all created containers
        self._getAndVerifyContainers(self.factory.create_count)

        # Getting another container should fail.
        self._verifyNoContainers()

        # Errors from the factory should have been logged.
        error_count = 0
        try:
            while True:
                self.assertEqual(TestException,
                                 type(self.pool.errors.get_nowait()))
                error_count += 1
        except Queue.Empty:
            pass
        self.assertGreater(error_count, 0)

        # Stop crashing, verify that the container pool recovers.
        self.factory.crash_on_create = False
        self._getAndVerifyContainers(1)


    def _getAndVerifyContainers(self, count):
        """Verifies that the test pool contains at least <count> containers."""
        for _ in range(count):
            # Block with timeout so that the test doesn't hang forever if
            # something goes wrong.  1 second should be sufficient because the
            # test factory is extremely lightweight.
            self.assertIsNotNone(self.pool.get(timeout=1))


    def _verifyNoContainers(self):
        self.assertIsNone(self.pool.get(timeout=1))


    def _forceWorkerTimeouts(self):
        """Forces worker thread timeouts. """
        # Set the container creation timeout to 0, wait for an error to occur,
        # then restore the old timeout.
        old_timeout = pool._CONTAINER_CREATION_TIMEOUT
        try:
            pool._CONTAINER_CREATION_TIMEOUT = 0
            while True:
                time.sleep(pool._MIN_MONITOR_PERIOD)
                try:
                    e = self.pool.errors.get_nowait()
                except Queue.Empty:
                    # While no errors, continue waiting.
                    pass
                else:
                    # Continue once a WorkerTimeoutError occurs.
                    if type(e) is pool_error.WorkerTimeoutError:
                        # Put the error back on the queue so tests get an
                        # accurate count of errors.
                        self.pool.errors.put(e)
                        break;
        finally:
            pool._CONTAINER_CREATION_TIMEOUT = old_timeout


class WorkerTests(unittest.TestCase):
    """Tests for the _Worker class."""

    def setUp(self):
        """Starts tests with a fully populated container pool."""
        self.factory = TestFactory()
        self.worker_results = Queue.Queue()
        self.worker_errors = Queue.Queue()


    def tearDown(self):
        """Cleans up the test pool."""


    def testGetResult(self):
        """Verifies that get_result transfers container ownership."""
        worker = self.createWorker()
        worker.start()
        worker.join(TEST_TIMEOUT)

        # Verify that one result was returned.
        self.assertIsNotNone(self.worker_results.get_nowait())
        with self.assertRaises(Queue.Empty):
            self.worker_results.get_nowait()

        self.assertNoWorkerErrors()


    def testThrottle(self):
        """Verifies that workers are properly throttled."""
        worker_max = pool._MAX_CONCURRENT_WORKERS
        workers = []
        self.factory.pause(worker_max * 2)
        # Create workers.  Check that the factory is getting called.
        for i in range(worker_max):
            worker = self.createWorker()
            worker.start()
            self.factory.wait(i+1)
            workers.append(worker)

        # Hack: verify that the throttle semaphore is fully depleted.  This
        # relies on implementation details, but there isn't really a way to test
        # that subsequent workers are halted.
        self.assertFalse(pool._Worker._throttle.acquire(False))

        # Create more workers (above the max).  Verify that the factory isn't
        # getting more create calls.
        for _ in range(worker_max):
            worker = self.createWorker()
            worker.start()
            while not worker.is_alive():
                time.sleep(0.1)
            self.assertEquals(worker_max, self.factory.create_count)

        for i in range(len(workers)):
            # Unblock one factory call.  Verify that another worker proceeds.
            self.factory.resume(1)
            self.factory.wait(worker_max + i)

        self.assertNoWorkerErrors()


    def testCancel_running(self):
        """Tests cancelling a worker while it's running."""
        worker = self.createWorker()

        self.factory.pause()
        worker.start()
        # Wait for the worker to call the factory.
        self.factory.wait(1)

        # Cancel the worker, then allow the factory call to proceed, then wait
        # for the worker to finish.
        worker.cancel()
        self.factory.resume()
        worker.join(TEST_TIMEOUT)

        # Verify that the container was destroyed.
        self.assertEqual(1, self.factory.destroy_count)

        # Verify that no results were received.
        with self.assertRaises(Queue.Empty):
            self.worker_results.get_nowait()

        self.assertNoWorkerErrors()


    def testCancel_completed(self):
        """Tests cancelling a worker after it's done."""
        worker = self.createWorker()

        # Start the worker and let it finish.
        worker.start()
        worker.join(TEST_TIMEOUT)

        # Cancel the worker after it completes.  Verify that this returns False.
        self.assertFalse(worker.cancel())

        # Verify that one result was delivered.
        self.assertIsNotNone(self.worker_results.get_nowait())
        with self.assertRaises(Queue.Empty):
            self.worker_results.get_nowait()

        self.assertNoWorkerErrors()


    def createWorker(self):
        """Creates a new pool worker for testing."""
        return pool._Worker(self.factory,
                            self.worker_results.put,
                            self.worker_errors.put)


    def assertNoWorkerErrors(self):
        """Fails if the error queue contains errors."""
        with self.assertRaises(Queue.Empty):
            e = self.worker_errors.get_nowait()
            logging.error('Unexpected worker error: %r', e)




class TestFactory(object):
    """A fake ContainerFactory for testing.

    Keeps track of the number of containers created and destroyed.  Includes
    synchronization so clients can wait for containers to be created.  Hangs and
    crashes on demand.
    """
    def __init__(self):
        self.create_cv = threading.Condition()
        self.create_count = 0
        self.lock_destroy_count = threading.Lock()
        self.destroy_count = 0
        self.crash_on_create = False
        self.hanging_ids = []


    def create_container(self):
        """Creates a fake Container.

        This method might crash or hang if the factory is set up to do so.

        @raises Exception: if crash_on_create is set to True on this factory.
        """
        if self.crash_on_create:
            raise TestException()
        with self.create_cv:
            next_id = self.create_count
            self.create_count += 1
            self.create_cv.notify()
        # Notify the condition variable before hanging, so that other
        # create_container calls are not affected.
        while next_id in self.hanging_ids or -1 in self.hanging_ids:
            time.sleep(0.1)

        return TestContainer(self)


    def pause(self, count=None):
        """Temporarily stops container creation.

        Calls to create_container will block until resume() is called.  Use this
        to simulate hanging/long container creation times.
        """
        if count is None:
            self.hanging_ids.append(-1)
        else:
            self.hanging_ids.extend(range(self.create_count,
                                          self.create_count + count))


    def resume(self, count=None):
        """Resumes container creation.

        @raises ThreadError: If the factory is not paused when this is called.
        """
        if count is None:
            self.hanging_ids = []
        else:
            self.hanging_ids = self.hanging_ids[count:]


    def wait(self, count):
        """Waits until the factory has created <count> containers.

        @param count: The number of container creations to wait for.
        """
        with self.create_cv:
            while self.create_count < count:
                self.create_cv.wait(TEST_TIMEOUT)


class TestContainer(object):
    """A fake Container class.

    This class does nothing aside from notifying its factory when it is
    destroyed.
    """

    def __init__(self, factory):
        self._factory = factory


    def destroy(self, *_args, **_kwargs):
        """Destroys the test container.

        A mock implementation of the real Container.destroy method.  Calls back
        to the TestFactory to notify it that a Container destruction has
        occurred.
        """
        with self._factory.lock_destroy_count:
            self._factory.destroy_count += 1


class TestException(Exception):
    """An exception class for the TestFactory to raise."""
    def __init__(self):
        super(TestException, self).__init__('test error')


if __name__ == '__main__':
    unittest_setup.setup(require_sudo=False)
    unittest.main()
