# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import threading
import time

import common
from autotest_lib.site_utils.lxc.container_pool import async_listener
from autotest_lib.site_utils.lxc.container_pool import error
from autotest_lib.site_utils.lxc.container_pool import message
from autotest_lib.site_utils.lxc.container_pool import multi_logger

try:
    import cPickle as pickle
except:
    import pickle


# The name of the linux domain socket used by the container pool.  Just one
# exists, so this is just a hard-coded string.
_SOCKET_NAME = 'container_pool_socket'
# The minimum period between polling for new connections, in seconds.
_MIN_POLLING_PERIOD = 0.1
_logger = multi_logger.create('container_pool_service')


class Service(object):
    """A manager for a pool of LXC containers.

    The Service class manages client communication with an underlying container
    pool.  It listens for incoming client connections, then spawns threads to
    deal with communication with each client.
    """

    def __init__(self, host_dir):
        """Sets up a new container pool service.

        @param host_dir: A SharedHostDir.  This will be used for Zygote
                         configuration as well as for general pool operation
                         (e.g. opening linux domain sockets for communication).
        """
        # Create socket for receiving container pool requests.  This also acts
        # as a mutex, preventing multiple container pools from being
        # instantiated.
        socket_path = os.path.join(host_dir.path, _SOCKET_NAME)
        self._connection_listener = async_listener.AsyncListener(socket_path)
        self._client_threads = []
        self._stop_event = None
        self._running = False


    def start(self):
        """Starts the service."""
        self._running = True

        # Start listening asynchronously for incoming connections.
        self._connection_listener.start()

        # Poll for incoming connections, and spawn threads to handle them.
        _logger.debug('Start event loop.')
        while self._stop_event is None:
            self._handle_incoming_connections()
            self._cleanup_closed_connections()
            time.sleep(_MIN_POLLING_PERIOD)

        _logger.debug('Exit event loop.')

        # Stopped - stop all the client threads, stop listening, then signal
        # that shutdown is complete.
        for thread in self._client_threads:
            thread.stop()
        try:
            self._connection_listener.close()
        except Exception as e:
            _logger.error('Error stopping pool service: %r', e)
            raise
        finally:
            # Make sure state is consistent.
            self._stop_event.set()
            self._stop_event = None
            self._running = False
            _logger.debug('Container pool stopped.')


    def stop(self):
        """Stops the service."""
        self._stop_event = threading.Event()
        return self._stop_event


    def is_running(self):
        """Returns whether or not the service is currently running."""
        return self._running


    def _handle_incoming_connections(self):
        """Checks for connections, and spawn sub-threads to handle requests."""
        connection = self._connection_listener.get_connection()
        if connection is not None:
            # Spawn a thread to deal with the new connection.
            thread = _ClientThread(self, connection)
            thread.start()
            self._client_threads.append(thread)
            _logger.debug('Client thread count: %d', len(self._client_threads))


    def _cleanup_closed_connections(self):
        """Cleans up dead client threads."""
        # We don't need to lock because all operations on self._client_threads
        # take place on the main thread.
        self._client_threads = [t for t in self._client_threads if t.is_alive()]


class _ClientThread(threading.Thread):
    """A class that handles communication with a pool client.

    Use a thread-per-connection model instead of select()/poll() for a few
    reasons:
    - the number of simultaneous clients is not expected to be high enough for
      select or poll to really pay off.
    - one thread per connection is more robust - if a single client somehow
      crashes its communication thread, that will not affect the other
      communication threads or the main pool service.
    """

    def __init__(self, service, connection):
        self._service = service
        self._connection = connection
        self._running = False
        super(_ClientThread, self).__init__(name='client_thread')


    def run(self):
        """Handles messages coming in from clients.

        The thread main loop monitors the connection and handles incoming
        messages.  Polling is used so that the loop condition can be checked
        regularly - this enables the thread to exit cleanly if required.

        Any kind of error will exit the event loop and close the connection.
        """
        _logger.debug('Start event loop.')
        try:
            self._running = True
            while self._running:
                # Poll and deal with messages every second.  The timeout enables
                # the thread to exit cleanly when stop() is called.
                if self._connection.poll(1):
                    msg = self._connection.recv()
                    response = self._handle_message(msg)
                    if response is not None:
                        self._connection.send(response)

        except EOFError:
            # The client closed the connection.
            _logger.debug('Connection closed.')

        except (AttributeError,
                ImportError,
                IndexError,
                pickle.UnpicklingError) as e:
            # Some kind of pickle error occurred.
            _logger.error('Error while unpickling message: %s', e)

        except error.UnknownMessageTypeError as e:
            # The message received was a valid python object, but not a valid
            # Message.
            _logger.error('Message error: %s', e)

        finally:
            # Always close the connection.
            _logger.debug('Exit event loop.')
            self._connection.close()


    def stop(self):
        """Stops the client thread."""
        self._running = False

    def _handle_message(self, msg):
        """Handles incoming messages."""

        # Only handle Message objects.
        if not isinstance(msg, message.Message):
            raise error.UnknownMessageTypeError(
                    'Invalid message class %s' % type(msg))

        response = None
        if msg.type == message.ECHO:
            # Just echo the message back, for testing aliveness.
            _logger.debug('Echo: %r', msg.args)
            response = msg

        elif msg.type == message.SHUTDOWN:
            _logger.debug('Received shutdown request.')
            self._service.stop().wait()
            _logger.debug('Service shutdown complete.')
            response = message.ack()

        else:
            raise error.UnknownMessageTypeError(
                    'Invalid message type %s' % msg.type)

        return response
