# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import httplib
import logging
import socket
import xmlrpclib

from autotest_lib.client.common_lib.cros import retry
from autotest_lib.client.cros import constants
from autotest_lib.server import autotest
from autotest_lib.server.cros.chameleon import audio_facade_adapter
from autotest_lib.server.cros.chameleon import display_facade_adapter


class RemoteFacadeConnection(object):
    """An abstraction of XML RPC connection to the DUT multimedia server.

    The traditional XML RPC server proxy is static. It is lost when DUT
    reboots. This class keeps track on this connection and returns the
    up-to-date XML RPC server proxy once DUT reboots.

    """

    XMLRPC_CONNECT_TIMEOUT = 60
    XMLRPC_RETRY_TIMEOUT = 180
    XMLRPC_RETRY_DELAY = 10

    def __init__(self, host):
        """Construct a RemoteFacadeConnection.

        @param host: Host object representing a remote host.
        """
        self._client = host
        self._xmlrpc_proxy = None
        self.connect()


    def connect(self):
        """Connects the XML-RPC proxy on the client."""
        @retry.retry((socket.error,
                      xmlrpclib.ProtocolError,
                      httplib.BadStatusLine),
                     timeout_min=self.XMLRPC_RETRY_TIMEOUT / 60.0,
                     delay_sec=self.XMLRPC_RETRY_DELAY)
        def connect_with_retries():
            """Connects the XML-RPC proxy with retries."""
            self._xmlrpc_proxy = self._client.xmlrpc_connect(
                    constants.MULTIMEDIA_XMLRPC_SERVER_COMMAND,
                    constants.MULTIMEDIA_XMLRPC_SERVER_PORT,
                    command_name=(
                        constants.MULTIMEDIA_XMLRPC_SERVER_CLEANUP_PATTERN
                    ),
                    ready_test_name=(
                        constants.MULTIMEDIA_XMLRPC_SERVER_READY_METHOD),
                    timeout_seconds=self.XMLRPC_CONNECT_TIMEOUT)

        logging.info('Setup the connection to RPC server, with retries...')
        connect_with_retries()


    @property
    def xmlrpc_proxy(self):
        """Gets the XML RPC server proxy object.

        @return XML RPC proxy to DUT multimedia server.
        """
        return self._xmlrpc_proxy


    def __del__(self):
        """Destructor of RemoteFacadeFactory."""
        self._client.rpc_disconnect(
                constants.MULTIMEDIA_XMLRPC_SERVER_PORT)


class RemoteFacadeFactory(object):
    """A factory to generate remote multimedia facades.

    The facade objects are remote-wrappers to access the DUT multimedia
    functionality, like display, video, and audio.

    """

    def __init__(self, host):
        """Construct a RemoteFacadeFactory.

        @param host: Host object representing a remote host.
        """
        self._client = host
        # Make sure the client library is on the device so that the proxy code
        # is there when we try to call it.
        client_at = autotest.Autotest(self._client)
        client_at.install()
        self._connection = RemoteFacadeConnection(self._client)


    def create_audio_facade(self):
        """Creates an audio facade object."""
        # TODO(cychiang): pass _client to AudioFacadeRemoteAdapter if needed.
        return audio_facade_adapter.AudioFacadeRemoteAdapter(
                self._connection)


    def create_display_facade(self):
        """Creates a display facade object."""
        return display_facade_adapter.DisplayFacadeRemoteAdapter(
                self._client, self._connection)
