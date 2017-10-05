#!/usr/bin/python
# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import array
import collections
import os
import shutil
import tempfile
import threading
import unittest
from contextlib import contextmanager
from multiprocessing import connection

import common
from autotest_lib.site_utils.lxc import unittest_setup
from autotest_lib.site_utils.lxc.container_pool import message
from autotest_lib.site_utils.lxc.container_pool import service
from autotest_lib.site_utils.lxc.container_pool import unittest_client


FakeHostDir = collections.namedtuple('FakeHostDir', ['path'])


class ServiceTests(unittest.TestCase):
    """Unit tests for the Service class."""

    @classmethod
    def setUpClass(cls):
        """Creates a directory for running the unit tests. """
        # Explicitly use /tmp as the tmpdir.  Board specific TMPDIRs inside of
        # the chroot are set to a path that causes the socket address to exceed
        # the maximum allowable length.
        cls.test_dir = tempfile.mkdtemp(prefix='service_unittest_', dir='/tmp')
        cls.host_dir = FakeHostDir(cls.test_dir)
        cls.address = os.path.join(cls.test_dir, service._SOCKET_NAME)


    @classmethod
    def tearDownClass(cls):
        """Deletes the test directory. """
        shutil.rmtree(cls.test_dir)


    def testConnection(self):
        """Tests a simple connection to the pool service."""
        with self.run_service():
            self.assertTrue(self._pool_is_healthy())


    def testAbortedConnection(self):
        """Tests that a closed connection doesn't crash the service."""
        with self.run_service():
            client = connection.Client(self.address)
            client.close()
            self.assertTrue(self._pool_is_healthy())


    def testCorruptedMessage(self):
        """Tests that corrupted messages don't crash the service."""
        with self.run_service(), self.create_client() as client:
            # Send a raw array of bytes.  This will cause an unpickling error.
            client.send_bytes(array.array('i', range(1, 10)))
            # Verify that the container pool closed the connection.
            with self.assertRaises(EOFError):
                client.recv()
            # Verify that the main container pool service is still alive.
            self.assertTrue(self._pool_is_healthy())


    def testInvalidMessageClass(self):
        """Tests that bad messages don't crash the service."""
        with self.run_service(), self.create_client() as client:
            # Send a valid object but not of the right Message class.
            client.send('foo')
            # Verify that the container pool closed the connection.
            with self.assertRaises(EOFError):
                client.recv()
            # Verify that the main container pool service is still alive.
            self.assertTrue(self._pool_is_healthy())


    def testInvalidMessageType(self):
        """Tests that messages with a bad type don't crash the service."""
        with self.run_service(), self.create_client() as client:
            # Send a valid object but not of the right Message class.
            client.send(message.Message('foo', None))
            # Verify that the container pool closed the connection.
            with self.assertRaises(EOFError):
                client.recv()
            # Verify that the main container pool service is still alive.
            self.assertTrue(self._pool_is_healthy())


    def testStop(self):
        """Tests stopping the service."""
        with self.run_service() as service, self.create_client() as client:
            self.assertTrue(service.is_running())
            client.send(message.shutdown())
            client.recv()  # wait for ack
            self.assertFalse(service.is_running())


    def testMultipleClients(self):
        """Tests multiple simultaneous connections."""
        with self.run_service():
            with self.create_client() as client0:
                with self.create_client() as client1:

                    msg0 = message.echo(
                        msg='two driven jocks help fax my big quiz')
                    msg1 = message.echo(
                        msg='how quickly daft jumping zebras vex')

                    client0.send(msg0)
                    client1.send(msg1)

                    echo0 = client0.recv()
                    echo1 = client1.recv()

                    self.assertEqual(msg0, echo0)
                    self.assertEqual(msg1, echo1)


    def _pool_is_healthy(self):
        """Verifies that the pool service is still functioning.

        Sends an echo message and tests for a response.  This is a stronger
        signal of aliveness than checking Service.is_running, but a False return
        value does not necessarily indicate that the pool service shut down
        cleanly.  Use Service.is_running to check that.
        """
        with self.create_client() as client:
            msg = message.echo(msg='foobar')
            client.send(msg)
            return client.recv() == msg


    @contextmanager
    def run_service(self):
        """Creates and cleans up a Service instance."""
        svc = service.Service(self.host_dir)
        thread = threading.Thread(name='service', target=svc.start)
        thread.start()
        try:
            yield svc
        finally:
            svc.stop()
            thread.join(1)


    @contextmanager
    def create_client(self):
        """Creates and cleans up a client connection."""
        client = unittest_client.connect(self.address)
        try:
            yield client
        finally:
            client.close()


if __name__ == '__main__':
    unittest_setup.setup()
    unittest.main()
