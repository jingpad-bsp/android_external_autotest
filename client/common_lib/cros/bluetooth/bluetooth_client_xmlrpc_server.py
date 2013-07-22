#!/usr/bin/env python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import logging.handlers

import common
from autotest_lib.client.common_lib.cros import xmlrpc_server
from autotest_lib.client.cros import constants


class BluetoothClientXmlRpcDelegate(xmlrpc_server.XmlRpcDelegate):
    """Exposes DUT methods called removely during Bluetooth autotests.

    All instance methods of this object without a preceding '_' are exposed via
    an XML-RPC server. This is not a stateless handler object, which means that
    if you store state inside the delegate, that state will remain aroun dfor
    future calls.
    """

    def __init__(self):
        pass


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = '/dev/log')
    logging.getLogger().addHandler(handler)
    logging.debug('bluetooth_client_xmlrpc_server main...')
    server = xmlrpc_server.XmlRpcServer(
            'localhost',
            constants.BLUETOOTH_CLIENT_XMLRPC_SERVER_PORT)
    server.register_delegate(BluetoothClientXmlRpcDelegate())
    server.run()
