# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import constants
from autotest_lib.server import autotest


class BluetoothTester(object):
    """BluetoothTester is a thin layer of logic over a remote tester."""

    XMLRPC_BRINGUP_TIMEOUT_SECONDS = 60

    @property
    def host(self):
        """@return host object representing the remote tester."""
        return self._host

    def __init__(self, tester_host):
        """Construct a BluetoothTester.

        @param tester_host host object representing a remote host.

        """
        self._host = tester_host
        # Make sure the client library is on the device so that the proxy code
        # is there when we try to call it.
        client_at = autotest.Autotest(self.host)
        client_at.install()
        # Start up the XML-RPC proxy on the tester.
        self._proxy = self.host.xmlrpc_connect(
                constants.BLUETOOTH_TESTER_XMLRPC_SERVER_COMMAND,
                constants.BLUETOOTH_TESTER_XMLRPC_SERVER_PORT,
                command_name=
                  constants.BLUETOOTH_TESTER_XMLRPC_SERVER_CLEANUP_PATTERN,
                ready_test_name=
                  constants.BLUETOOTH_TESTER_XMLRPC_SERVER_READY_METHOD,
                timeout_seconds=self.XMLRPC_BRINGUP_TIMEOUT_SECONDS)

    def close(self):
        """Tear down state associated with the client."""
        # This kills the RPC server.
        self._host.close()
