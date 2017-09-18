#!/usr/bin/python
# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import Queue
import threading
import unittest

import common
from autotest_lib.client.common_lib import error
from autotest_lib.site_utils.lxc import unittest_setup
from autotest_lib.site_utils.lxc.container_pool import pool


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


    @unittest.skip('not working yet')
    def testShutdown_hungFactory(self):
        """Verifies that a hung factory does not prevent clean shutdown."""
        factory = TestFactory()
        factory.pause()
        self._createAndDestroyPool(factory, 3, wait=False)


    def _createAndDestroyPool(self, factory, size, wait=True):
        """Creates a container pool, fully populates it, then destroys it.

        @param factory: A ContainerFactory to use for the Pool.
        @param size: The size of the Pool to create.
        """
        test_pool = pool.Pool(factory, size=size)

        # Wait for the pool to be fully populated.
        if wait:
            factory.wait(size)

        # Clean up the container pool.  pedantic=True raises errors if the
        # pool's worker thread does not shut down properly.
        try:
            test_pool.cleanup(pedantic=True)
        except threading.ThreadError:
            self.fail('Error while cleaning up container pool:\n%s' %
                      error.format_error())


class PoolTests(unittest.TestCase):
    """Unit tests for the Pool class."""

    # Explicit pool size, for testing.
    POOL_SIZE = 5

    def setUp(self):
        """Starts tests with a fully populated container pool."""
        self.factory = TestFactory()
        self.pool = pool.Pool(self.factory, size=self.POOL_SIZE)
        # Wait for the pool to be fully populated.
        self.factory.wait(self.POOL_SIZE)


    def tearDown(self):
        """Cleans up the test pool."""
        self.pool.cleanup(pedantic=True)


    def testRequestContainer(self):
        """Tests requesting a container from the pool."""
        for _ in range(self.POOL_SIZE + 10):
            try:
                # Block with timeout so that the test doesn't hang forever if
                # something goes wrong.  1 second should be sufficient because
                # the test factory is extremely lightweight.
                self.assertIsNotNone(self.pool.get(timeout=1))
            except Queue.Empty:
                self.fail('Container pool failed to supply a container.')


    def testRequestContainer_factoryHung(self):
        """Tests pool recovery from a hung container factory."""
        # Simulate the factory hanging.
        self.factory.pause()

        # Get all created containers
        for _ in range(self.factory.create_count):
            self.assertIsNotNone(self.pool.get(timeout=1))

        # Getting another container should fail.
        self.assertIsNone(self.pool.get(timeout=1))

        # Restart the factory, verify that the container pool recovers.
        self.factory.resume()
        self.assertIsNotNone(self.pool.get(timeout=1))


    def testRequestContainer_factoryCrashed(self):
        """Tests pool operation when the factory worker dies."""
        # Cause the factory to crash when create is called.
        self.factory.crash_on_create = True

        # Get all created containers
        for _ in range(self.factory.create_count):
            self.assertIsNotNone(self.pool.get(timeout=1))

        # Getting another container should fail.
        self.assertIsNone(self.pool.get(timeout=1))

        # Errors from the factory should have been logged.
        errors = self.pool.errors
        self.assertGreater(len(errors), 0)
        for e in errors:
            self.assertEqual(TestException, type(e))

        # Stop crashing, verify that the container pool recovers.
        self.factory.crash_on_create = False
        self.assertIsNotNone(self.pool.get(timeout=1))


class TestFactory(object):
    """A fake ContainerFactory for testing.

    Keeps track of the number of containers created and destroyed.  Includes
    synchronization so clients can wait for containers to be created.  Hangs and
    crashes on demand.
    """
    def __init__(self):
        self.create_lock = threading.Lock()
        self.create_cv = threading.Condition(self.create_lock)
        self.create_count = 0
        self.destroy_count = 0
        self.crash_on_create = False


    def create_container(self):
        """Creates a fake Container.

        This method might crash or hang if the factory is set up to do so.

        @raises Exception: if crash_on_create is set to True on this factory.
        """
        if self.crash_on_create:
            raise TestException()
        with self.create_cv:
            self.create_count += 1
            self.create_cv.notify()
        return TestContainer(self)


    def pause(self):
        """Temporarily stops container creation.

        Calls to create_container will block until resume() is called.  Use this
        to simulate hanging/long container creation times.
        """
        self.create_lock.acquire()


    def resume(self):
        """Resumes container creation.

        @raises ThreadError: If the factory is not paused when this is called.
        """
        self.create_lock.release()


    def wait(self, count):
        """Waits until the factory has created <count> containers.

        @param count: The number of container creations to wait for.
        """
        with self.create_cv:
            while self.create_count < count:
                self.create_cv.wait()


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
        self._factory.destroy_count += 1


class TestException(Exception):
    """An exception class for the TestFactory to raise."""


if __name__ == '__main__':
    unittest_setup.setup(require_sudo=False)
    unittest.main()
