#!/usr/bin/python
# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import shutil
import socket
import tempfile
import threading
import unittest
from multiprocessing import connection

import common
from autotest_lib.client.common_lib import error
from autotest_lib.site_utils.lxc import unittest_setup
from autotest_lib.site_utils.lxc.container_pool import async_listener


# Namespace object for parsing cmd line options.
options = None


class AsyncListenerTests(unittest.TestCase):
    """Unit tests for the AsyncListener class."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.address = os.path.join(self.tmpdir, 'socket')
        self.authkey = 'foo'
        self.listener = async_listener.AsyncListener(self.address,
                                                     authkey=self.authkey)


    def tearDown(self):
        self.listener.close()
        shutil.rmtree(self.tmpdir)


    def testInvalidAddresses(self):
        """Verifies that invalid socket paths raise errors."""
        with self.assertRaises(socket.error):
            invalid_address = os.path.join(self.tmpdir, 'foo', 'socket')
            async_listener.AsyncListener(invalid_address, authkey=self.authkey)


    def testAddressConflict(self):
        """Verifies that address conflicts raise errors."""
        with self.assertRaises(socket.error):
            async_listener.AsyncListener(self.address, authkey=self.authkey)


    def testInetAddresses(self):
        """Verifies that inet addresses raise errors."""
        with self.assertRaises(TypeError):
            async_listener.AsyncListener(('127.0.0.1', 0), authkey=self.authkey)


    def testStartStop(self):
        """Tests starting and stopping the async listener."""
        try:
            self.assertFalse(self.listener.is_running())

            self.listener.start()
            self.assertTrue(self.listener.is_running())

            # Establish a connection to verify that the listener is actually
            # alive.
            host, client = self._make_connection()
            client.close()
            host.close()

            self.assertTrue(self.listener.stop())
            self.assertFalse(self.listener.is_running())
        except:
            self.fail(error.format_error())


    def testStop_notRunning(self):
        """Tests stopping the async listener when it's not running."""
        try:
            self.assertFalse(self.listener.is_running())
            # Verify that calling stop just returns False when the listener
            # isn't running.
            self.assertFalse(self.listener.stop())
        except:
            self.fail(error.format_error())


    def testConnection(self):
        """Tests starting a connection."""
        self.listener.start()

        # Verify no pending connections.
        self.assertIsNone(self.listener.get_connection(timeout=1))

        # Start a client connection, verify that the listener now returns a
        # pending connection.  Keep a reference to the client, so it doesn't get
        # GC'd while the test is in progress.
        _unused = connection.Client(self.address, authkey=self.authkey)
        self.assertIsNotNone(self.listener.get_connection(timeout=1))


    def testAuthFailure(self):
        """Tests connections with failed authentication."""
        self.listener.start()

        # Verify that a bad auth key results in a failed connection.
        with self.assertRaises(connection.AuthenticationError):
            _unused = connection.Client(self.address,
                                        authkey=self.authkey+'foo')
        self.assertIsNone(self.listener.get_connection(timeout=1))

        # Verify that subsequent connections still work.
        _unused = connection.Client(self.address, authkey=self.authkey)
        self.assertIsNotNone(self.listener.get_connection(timeout=1))


    def testHostToClientComms(self):
        """Tests that client/host connections can exchange data."""
        self.listener.start()
        host, client = self._make_connection()

        # Send a message on the host side socket, check that the client receives
        # it.
        msg = 'quickly moving jedi zap a brown sith fox'
        host.send(msg)
        received_msg = client.recv()
        self.assertEqual(msg, received_msg)


    def testMultipleConnections(self):
        """Tests for correct pairing of multiple host/client connections."""
        self.listener.start()

        # Create two sets of host/client connections.  Verify that messages sent
        # on each client are received by the correct respective host.
        host0, client0 = self._make_connection()
        host1, client1 = self._make_connection()

        msg0 = 'a large fawn jumped quickly over white zinc boxes'
        msg1 = 'six big devils from japan quickly forgot how to waltz'

        client0.send(msg0)
        client1.send(msg1)

        received_msg0 = host0.recv()
        received_msg1 = host1.recv()

        self.assertEquals(msg0, received_msg0)
        self.assertEquals(msg1, received_msg1)


    def _make_connection(self):
        """Creates pairs of host/client connections.

        @return: A host, client connection pair.
        """
        client = _ClientFactory(self.address, authkey=self.authkey).connect()
        host = self.listener.get_connection(timeout=1)
        return host, client


class _ClientFactory(threading.Thread):
    """Factory class for making client connections with a timeout.

    Instantiate this with an address and a key, and call make_connection.  If a
    connection is not established within a set period of time, the
    make_connction call will raise a socket.timeout exception instead of hanging
    indefinitely.
    """
    def __init__(self, address, authkey):
        super(_ClientFactory, self).__init__()
        # Use a daemon thread, so that if this thread hangs, it doesn't keep the
        # parent thread alive.  All daemon threads die when the parent process
        # dies.
        self.daemon = True
        self._address = address
        self._authkey = authkey
        self._client = None


    def run(self):
        """Instantiates a connection.Client."""
        self._client = connection.Client(self._address, authkey=self._authkey)


    def connect(self):
        """Attempts to create a connection.Client with a timeout.

        @return: A connection.Client connected using the address and authkey
                 that were specified when this factory was created.

        @raises socket.timeout: If the connection is not established after 1
                                second.
        """
        # Start the thread, which attempts to open the connection.  Wait one
        # second for the connection to complete, and if it does not, raise a
        # timeout exception.
        self.start()
        self.join(1)
        if self._client is not None:
            return self._client
        else:
            raise socket.timeout('timed out')


if __name__ == '__main__':
    unittest_setup.setup()
    unittest.main()
