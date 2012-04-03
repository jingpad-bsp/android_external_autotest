# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""RemotePyAuto: Exposes the PyAuto interface over HTTP.

RemotePyAuto launches a local PyAuto instance and exposes the interface to
remote clients over HTTP using XMLRPC. Expects the PyAuto Autotest dependency
to be installed.
"""

import logging, os, sys
from SimpleXMLRPCServer import SimpleXMLRPCServer

import constants, cros_ui, cryptohome, login

# Import the pyauto module
# This can be done only after pyauto_dep dependency has been installed.
pyautolib_dir = os.path.join(
    os.path.dirname(__file__), os.pardir, 'deps', 'pyauto_dep',
    'test_src', 'chrome', 'test', 'pyautolib')
assert os.path.isdir(pyautolib_dir), '%s missing.' % pyautolib_dir
sys.path.append(pyautolib_dir)
import pyauto


class RemotePyAuto(pyauto.PyUITest):
    """Launches an XMLRPC server to handle remote PyAuto commands."""


    def __init__(self, methodName='runTest'):
        pyauto.PyUITest.__init__(self, methodName, clear_profile=False)


    def testXMLRPCserve(self):
        """Launches the XMLRPC server to provide PyAuto commands."""
        rpc_port = 9988
        server = SimpleXMLRPCServer(('localhost', rpc_port), allow_none=True)
        server.register_introspection_functions()
        server.register_instance(self)
        logging.info('XMLRPC Server: Serving PyAuto on port %s' % rpc_port)
        server.serve_forever()


    def LoginToDefaultAccount(self):
        """Login to ChromeOS using $default testing account."""
        creds = constants.CREDENTIALS['$default']
        username = cryptohome.canonicalize(creds[0])
        passwd = creds[1]
        self.Login(username, passwd)
        assert self.GetLoginInfo()['is_logged_in']
        logging.info('Logged in as %s' % username)


    def AppendTab(self, url):
        """Wrapper around AppendTab() that takes a url as a string.

        This is necessary because RPCXML is unable pass the object
        returned by pyauto.GURL().
        """
        return pyauto.PyUITest.AppendTab(self, pyauto.GURL(url))


    def cleanup(self):
        """Clean up after a PyAuto test.

        Replacement for the cleanup normally called at the end of a PyAuto test.
        Must be called manually at the end of the server side test.
        """
        self.tearDown()
        #reset UI
        cros_ui.nuke()


if __name__ == '__main__':
  pyauto.Main()
