# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

CROS_P2P_PROTO = '_cros_p2p._tcp'
CROS_P2P_PORT = 16725

class CrosP2PDaemon(object):
    """Simulates a P2P server.

    The simulated P2P server will instruct the underlying ZeroconfDaemon to
    reply to requests sharing the files registered on this server.
    """

    def __init__(self, zeroconf, port=CROS_P2P_PORT):
        """Initialize the CrosP2PDaemon.

        @param zeroconf: A ZeroconfDaemon instance where this P2P server will be
        announced.
        @param port: The port where the HTTP server part of the P2P protocol is
        listening. The HTTP server is assumend to be running on the same host as
        the provided ZeroconfDaemon server.
        """
        self._zeroconf = zeroconf
        self._files = {}
        self._num_connections = 0

        self._p2p_domain = CROS_P2P_PROTO + '.' + zeroconf.domain
        # Register the HTTP Server.
        zeroconf.register_SRV(zeroconf.hostname, CROS_P2P_PROTO, 0, 0, port)
        # Register the P2P running on this server.
        zeroconf.register_PTR(self._p2p_domain, zeroconf.hostname)
        self._update_records()


    def add_file(self, file_id, file_size):
        """Add or update a shared file.

        @param file_id: The name of the file (without .p2p extension).
        @param file_size: The expected total size of the file.
        """
        self._files[file_id] = file_size
        self._update_records()


    def remove_file(self, file_id):
        """Remove a shared file.

        @param file_id: The name of the file (without .p2p extension).
        """
        del self._files[file_id]
        self._update_records()


    def set_num_connections(self, num_connections):
        """Sets the number of connections that the HTTP server is handling.

        This method allows the P2P server to properly announce the number of
        connections it is currently handling.

        @param num_connections: An integer with the number of connections.
        """
        self._num_connections = num_connections
        self._update_records()


    def _update_records(self):
        # Build the TXT records:
        txts = ['num_connections=%d' % self._num_connections]
        for file_id, file_size in self._files.iteritems():
            txts.append('id_%s=%d' % (file_id, file_size))
        self._zeroconf.register_TXT(
            self._zeroconf.hostname + '.' + self._p2p_domain, txts)
