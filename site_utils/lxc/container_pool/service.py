# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import threading
import time

import common
from autotest_lib.site_utils.lxc import base_image
from autotest_lib.site_utils.lxc import constants
from autotest_lib.site_utils.lxc import container_factory
from autotest_lib.site_utils.lxc import zygote
from autotest_lib.site_utils.lxc.container_pool import async_listener
from autotest_lib.site_utils.lxc.container_pool import error
from autotest_lib.site_utils.lxc.container_pool import message
from autotest_lib.site_utils.lxc.container_pool import pool

try:
    import cPickle as pickle
except:
    import pickle


# The minimum period between polling for new connections, in seconds.
_MIN_POLLING_PERIOD = 0.1


class Service(object):
    """A manager for a pool of LXC containers.

    The Service class manages client communication with an underlying container
    pool.  It listens for incoming client connections, then spawns threads to
    deal with communication with each client.
    """

    def __init__(self, host_dir, pool=None):
        """Sets up a new container pool service.

        @param host_dir: A SharedHostDir.  This will be used for Zygote
                         configuration as well as for general pool operation
                         (e.g. opening linux domain sockets for communication).
        @param pool: (for testing) A container pool that the service will
                     maintain.  This parameter exists for DI, for testing.
                     Under normal circumstances the service instantiates the
                     container pool internally.
        """
        # Create socket for receiving container pool requests.  This also acts
        # as a mutex, preventing multiple container pools from being
        # instantiated.
        self._socket_path = os.path.join(
                host_dir.path, constants.DEFAULT_CONTAINER_POOL_SOCKET)
        self._connection_listener = async_listener.AsyncListener(
                self._socket_path)
        self._client_threads = []
        self._stop_event = None
        self._running = False
        self._pool = pool


    def start(self, pool_size=constants.DEFAULT_CONTAINER_POOL_SIZE):
        """Starts the service.

        @param pool_size: The desired size of the container pool.  This
                          parameter has no effect if a pre-created pool was DI'd
                          into the Service constructor.
        """
        self._running = True

        # Start the container pool.
        if self._pool is None:
            factory = container_factory.ContainerFactory(
                    base_container=base_image.BaseImage().get(),
                    container_class=zygote.Zygote)
            self._pool = pool.Pool(factory=factory, size=pool_size)

        # Start listening asynchronously for incoming connections.
        self._connection_listener.start()

        # Poll for incoming connections, and spawn threads to handle them.
        logging.debug('Start event loop.')
        while self._stop_event is None:
            self._handle_incoming_connections()
            self._cleanup_closed_connections()
            # TODO(kenobi): Poll for and log errors from pool.
            time.sleep(_MIN_POLLING_PERIOD)

        logging.debug('Exit event loop.')

        # Stopped - stop all the client threads, stop listening, then signal
        # that shutdown is complete.
        for thread in self._client_threads:
            thread.stop()
        try:
            self._connection_listener.close()
        except Exception as e:
            logging.error('Error stopping pool service: %r', e)
            raise
        finally:
            # Clean up the container pool.
            self._pool.cleanup()
            # Make sure state is consistent.
            self._stop_event.set()
            self._stop_event = None
            self._running = False
            logging.debug('Container pool stopped.')


    def stop(self):
        """Stops the service."""
        self._stop_event = threading.Event()
        return self._stop_event


    def is_running(self):
        """Returns whether or not the service is currently running."""
        return self._running


    def get_status(self):
        """Returns a dictionary of values describing the current status."""
        status = {}
        status['running'] = self._running
        status['socket_path'] = self._socket_path
        if self._running:
            status['pool capacity'] = self._pool.capacity
            status['pool size'] = self._pool.size
            status['pool worker count'] = self._pool.worker_count
            status['pool errors'] = self._pool.errors.qsize()
        return status


    def _handle_incoming_connections(self):
        """Checks for connections, and spawn sub-threads to handle requests."""
        connection = self._connection_listener.get_connection()
        if connection is not None:
            # Spawn a thread to deal with the new connection.
            thread = _ClientThread(self, connection)
            thread.start()
            self._client_threads.append(thread)
            logging.debug('Client thread count: %d', len(self._client_threads))


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
        logging.debug('Start event loop.')
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
            logging.debug('Connection closed.')

        except (AttributeError,
                ImportError,
                IndexError,
                pickle.UnpicklingError) as e:
            # Some kind of pickle error occurred.
            logging.error('Error while unpickling message: %s', e)

        except error.UnknownMessageTypeError as e:
            # The message received was a valid python object, but not a valid
            # Message.
            logging.error('Message error: %s', e)

        finally:
            # Always close the connection.
            logging.debug('Exit event loop.')
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

        if msg.type == message.ECHO:
            return self._echo(msg)
        elif msg.type == message.SHUTDOWN:
            return self._shutdown()
        elif msg.type == message.STATUS:
            return self._status()
        else:
            raise error.UnknownMessageTypeError(
                    'Invalid message type %s' % msg.type)


    def _echo(self, msg):
        """Handles ECHO messages.

        @param msg: A string that will be echoed back to the client.
        """
        # Just echo the message back, for testing aliveness.
        logging.debug('Echo: %r', msg.args)
        return msg


    def _shutdown(self):
        """Handles SHUTDOWN messages."""
        logging.debug('Received shutdown request.')
        # Request shutdown.  Wait for the service to actually stop before
        # sending the response.
        self._service.stop().wait()
        logging.debug('Service shutdown complete.')
        return message.ack()


    def _status(self):
        """Handles STATUS messages."""
        logging.debug('Received status request.')
        return self._service.get_status()
