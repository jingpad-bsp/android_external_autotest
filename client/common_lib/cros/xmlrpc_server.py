# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import errno
import logging
import select
import signal
import threading
import SimpleXMLRPCServer


class XmlRpcServer(threading.Thread):
    """Simple XMLRPC server implementation.

    In theory, Python should provide a sane XMLRPC server implementation as
    part of its standard library.  In practice the provided implementation
    doesn't handle signals, not even EINTR.  As a result, we have this class.

    Usage:

    server = XmlRpcServer(('localhost', 43212))
    server.register_delegate(my_delegate_instance)
    server.run()

    """

    def __init__(self, host, port):
        """Construct an XmlRpcServer.

        @param host string hostname to bind to.
        @param port int port number to bind to.

        """
        super(XmlRpcServer, self).__init__()
        logging.info('Binding server to %s:%d', host, port)
        self._server = SimpleXMLRPCServer.SimpleXMLRPCServer((host, port))
        self._server.register_introspection_functions()
        self._keep_running = True
        # Gracefully shut down on signals.  This is how we expect to be shut
        # down by autotest.
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)


    def register_delegate(self, delegate):
        """Register delegate objects with the server.

        The server will automagically look up all methods not prefixed with an
        underscore and treat them as potential RPC calls.  These methods may
        only take basic Python objects as parameters, as noted by the
        SimpleXMLRPCServer documentation.  The state of the delegate is
        persisted across calls.

        @param delegate object Python object to be exposed via RPC.

        """
        self._server.register_instance(delegate)


    def run(self):
        """Block and handle many XmlRpc requests."""
        logging.info('XmlRpcServer starting...')
        while self._keep_running:
            try:
                self._server.handle_request()
            except select.error as v:
                # In a cruel twist of fate, the python library doesn't handle
                # this kind of error.
                if v[0] != errno.EINTR:
                    raise
        logging.info('XmlRpcServer exited.')


    def _handle_signal(self, _signum, _frame):
        """Handle a process signal by gracefully quitting.

        SimpleXMLRPCServer helpfully exposes a method called shutdown() which
        clears a flag similar to _keep_running, and then blocks until it sees
        the server shut down.  Unfortunately, if you call that function from
        a signal handler, the server will just hang, since the process is
        paused for the signal, causing a deadlock.  Thus we are reinventing the
        wheel with our own event loop.

        """
        self._keep_running = False
