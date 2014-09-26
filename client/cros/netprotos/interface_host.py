# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import socket
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import interface


class InterfaceHost(object):
    """A host for use with ZeroconfDaemon that binds to an interface."""

    @property
    def ip_addr(self):
        """Get the IP address of the interface we're bound to."""
        return self._interface.ipv4_address


    def __init__(self, interface_name):
        self._interface = interface.Interface(interface_name)
        self._socket = None


    def close(self):
        """Close the underlying socket."""
        if self._socket:
            self._socket.close()


    def socket(self, family, sock_type):
        """Get a socket bound to this interface.

        Only supports IPv4 UDP sockets on broadcast addresses.

        @param family: must be socket.AF_INET.
        @param sock_type: must be socket.SOCK_DGRAM.

        """
        if family != socket.AF_INET or sock_type != socket.SOCK_DGRAM:
            raise error.TestError('InterfaceHost only understands UDP sockets.')
        if self._socket is not None:
            raise error.TestError('InterfaceHost only supports a single '
                                  'multicast socket.')

        self._socket = InterfaceDatagramSocket(self.ip_addr)
        return self._socket


    def run_until(self, predicate, timeout_seconds):
        """Handle traffic from our socket until |predicate|() is true.

        @param predicate: function without arguments that returns True or False.
        @param timeout_seconds: number of seconds to wait for predicate to
                                become True.
        @return: tuple(success, duration) where success is True iff predicate()
                 became true before |timeout_seconds| passed.

        """
        start_time = time.time()
        duration = lambda: time.time() - start_time
        while duration() < timeout_seconds:
            if predicate():
                return True, duration()
            # Assume this take non-trivial time, don't sleep here.
            self._socket.run_once()
        return False, duration()


class InterfaceDatagramSocket(object):
    """Broadcast UDP socket bound to a particular network interface."""

    # Wait for a UDP frame to appear for this long before timing out.
    TIMEOUT_VALUE_SECONDS = 0.5

    def __init__(self, interface_ip):
        """Construct an instance.

        @param interface_ip: string like '239.192.1.100'.

        """
        self._interface_ip = interface_ip
        self._recv_callback = None
        self._sock = None


    def close(self):
        """Close state associated with this object."""
        if self._sock is None:
            return
        # Closing the socket drops membership groups.
        self._sock.close()
        self._sock = None


    def listen(self, ip_addr, port, recv_callback):
        """Bind and listen on the ip_addr:port.

        @param ip_addr: Multicast group IP (e.g. '224.0.0.251')
        @param port: Local destination port number.
        @param recv_callback: A callback function that accepts three arguments,
                              the received string, the sender IPv4 address and
                              the sender port number.

        """
        if self._recv_callback is not None:
            raise error.TestError('listen() called twice on '
                                  'InterfaceDatagramSocket.')
        # Assume we're listening on a multicast UDP address.
        self._listen_ip = ip_addr
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_TTL, 20)
        self._sock.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP,
                              socket.inet_aton(self._listen_ip) +
                              socket.inet_aton(self._interface_ip))
        self._sock.settimeout(self.TIMEOUT_VALUE_SECONDS)
        self._sock.bind(('', port))
        self._recv_callback = recv_callback


    def run_once(self):
        """Receive pending frames if available, return after timeout otw."""
        if self._sock is None:
            raise error.TestError('Must listen() on socket before recv\'ing.')
        BUFFER_SIZE_BYTES = 2048
        try:
            data, sender_addr = self._sock.recvfrom(BUFFER_SIZE_BYTES)
        except socket.timeout:
            return
        if len(sender_addr) != 2:
            logging.error('Unexpected address: %r', sender_addr)
        self._recv_callback(data, *sender_addr)


    def send(self, data, ip_addr, port):
        """Send |data| to an IPv4 address.

        @param data: string of raw bytes to send.
        @param ip_addr: string like '239.192.1.100'.
        @param port: int like 50000.

        """
        self._sock.sendto(data, (ip_addr, port))
