# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server import autotest

_PYAUTO_INSTALLER = 'desktopui_PyAutoInstall'
_PYAUTO_REMOTE = ('python /usr/local/autotest/cros/remote_pyauto.py'
                  ' --no-http-server')
_PYAUTO_PORT = 9988
_PYAUTO_CLEANUP_NAME = 'remote_pyauto'

_PYAUTO_TIMEOUT = 10


def create_pyauto_proxy(host, auto_login=False):
    """Create a server-side proxy to a PyAuto client.

    This function ensures that the the PyAuto dependencies are
    installed on the given client host, starts an XMLRPC server on
    the host to serve PyAuto requests, and returns a proxy object
    for making calls to the remote PyAuto server.

    If this function is called more than once for a host, any proxy
    objects returned from previous calls will lose their connection.
    Additionally, installation restarts Chrome on the target.

    This function waits until the remote server is up and serving
    requests.  If the server times out, the function re-raises the
    last exception raised while attempting to connect.

    @param host The autotest client where PyAuto should be installed
                and run.
    @param auto_login If True, the PyAuto client will log in to the
                      default account prior to returning.
    """
    autotest_client = autotest.Autotest(host)
    autotest_client.run_test(_PYAUTO_INSTALLER, auto_login=auto_login)

    return host.xmlrpc_connect(_PYAUTO_REMOTE, _PYAUTO_PORT,
                               command_name=_PYAUTO_CLEANUP_NAME,
                               ready_test_name='IsChromeOS',
                               timeout_seconds=_PYAUTO_TIMEOUT)
