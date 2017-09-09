# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import Queue
import logging
import socket
import threading
from multiprocessing import connection


def _setup_logger():
    """Creates a custom logger for better multithreaded logging."""
    logger = logging.getLogger('container_pool')
    handler = logging.StreamHandler()
    handler.setFormatter(
            logging.Formatter('%(asctime)s [%(threadName)s] %(message)s'))
    logger.addHandler(handler)
    logger.propagate = False
    return logger
_logger = _setup_logger()


class AsyncListener(object):
    """A class for asynchronous listening on a unix socket.

    This class opens a unix socket with the given address and auth key.
    Connections are listened for on a separate thread, and queued up to be dealt
    with.
    """
    def __init__(self, address, authkey):
        """Opens a socket with the given address and key.

        @param address: The socket address.
        @param authkey: The authentication key (a string).

        @raises socket.error: If the address is already in use or is not a valid
                              path.
        @raises TypeError: If the address is not a valid unix domain socket
                           address.
        """
        self._socket = connection.Listener(address,
                                           family='AF_UNIX',
                                           authkey=authkey)
        self._address = address
        self._authkey = authkey
        self._queue = Queue.Queue()
        self._thread = None
        self._running = False


    def start(self):
        """Starts listening for connections.

        Starts a child thread that listens asynchronously for connections.
        After calling this function, incoming connections may be retrieved by
        calling the get_connection method.
        """
        logging.info('Starting connection listener.')
        self._running = True
        self._thread = threading.Thread(name='connection_listener',
                                        target=self._poll)
        self._thread.start()


    def is_running(self):
        """Returns whether the listener is currently running."""
        return self._running


    def stop(self):
        """Stop listening for connections.

        Stops the listening thread.  After this is called, connections will no
        longer be received by the socket.  Note, however, that the socket is not
        destroyed and that calling start again, will resume listening for
        connections.

        This function is expected to be called when the container pool service
        is being killed/restarted, so it doesn't make an extraordinary effort to
        ensure that the listener thread is cleanly destroyed.

        @return: True if the listener thread was successfully killed, False
                 otherwise.
        """
        if not self._running:
            return False

        _logger.info('Stopping connection listener.')
        # Setting this to false causes the thread's event loop to exit on the
        # next iteration.
        self._running = False
        # Initiate a connection to force a trip through the event loop.  Use raw
        # sockets because the connection module's convenience classes don't
        # support timeouts, which leads to deadlocks.
        try:
            fake_connection = socket.socket(socket.AF_UNIX)
            fake_connection.settimeout(0)  # non-blocking
            fake_connection.connect(self._address)
            fake_connection.close()
        except socket.timeout:
            _logger.error('Timeout while attempting to close socket listener.')
            return False

        _logger.info('Socket closed. Waiting for thread to terminate.')
        self._thread.join(1)
        return not self._thread.isAlive()


    def close(self):
        """Closes and destroys the socket.

        If the listener thread is running, it is first stopped.
        """
        if self._running:
            self.stop()
        self._socket.close()


    def get_connection(self, timeout=0):
        """Returns a connection, if one is pending.

        The listener thread queues up connections for the main process to
        handle.  This method returns a pending connection on the queue.  If no
        connections are pending, None is returned.

        @param timeout: Optional timeout.  If set to 0 (the default), the method
                        will return instantly if no connections are awaiting.
                        Otherwise, the method will wait the specified number of
                        seconds before returning.

        @return: A pending connection, or None of no connections are pending.
        """
        try:
            return self._queue.get(block=timeout>0, timeout=timeout)
        except Queue.Empty:
            return None


    def _poll(self):
        """Polls the socket for incoming connections.

        This function is intended to be run on the listener thread.  It listens
        for and accepts incoming socket connections.  Authenticated connections
        are placed on the queue of incoming connections.  Unauthenticated
        connections are logged and dropped.
        """
        _logger.debug('Entering connection listener event loop...')
        while self._running:
            _logger.debug('Listening for connection')
            try:
                self._queue.put(self._socket.accept())
                _logger.debug('Received connection from %s',
                              self._socket.last_accepted)
            except connection.AuthenticationError as e:
                _logger.error('Authentication failure: %s', e)
            except IOError:
                # The stop method uses a fake connection to unblock the polling
                # thread.  This results in an IOError but this is an expected
                # outcome.
                _logger.debug('Connection aborted.')
