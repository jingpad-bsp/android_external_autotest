# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import httplib, logging, os, socket, stat, time, utils
from autotest_lib.client.bin import chromeos_constants, site_cryptohome
from autotest_lib.client.common_lib import error, site_httpd

class GoogleAuthServer(object):
    """A mock Google accounts server that can be run in a separate thread
    during autotests. By default, it returns happy-signals, accepting any
    credentials.
    """

    sid = '1234'
    lsid = '5678'
    token = 'aaaa'


    def __init__(self,
                 cert_path='/etc/fake_root_ca/mock_server.pem',
                 key_path='/etc/fake_root_ca/mock_server.key',
                 port=443,
                 cl_responder=None,
                 it_responder=None,
                 ta_responder=None):
        self._client_login = chromeos_constants.CLIENT_LOGIN_URL
        self._issue_token = chromeos_constants.ISSUE_AUTH_TOKEN_URL
        self._token_auth = chromeos_constants.TOKEN_AUTH_URL
        self._test_over = '/webhp'

        self._testServer = site_httpd.SecureHTTPListener(port=port,
                                                         cert_path=cert_path,
                                                         key_path=key_path,
                                                         docroot=None)
        sa = self._testServer.getsockname()
        logging.info('Serving HTTPS on %s, port %s' % (sa[0], sa[1]))

        if cl_responder is None:
            cl_responder = self.__client_login_responder
        if it_responder is None:
            it_responder = self.__issue_token_responder
        if ta_responder is None:
            ta_responder = self.__token_auth_responder

        self._testServer.add_url_handler(self._client_login, cl_responder)
        self._testServer.add_url_handler(self._issue_token, it_responder)
        self._testServer.add_url_handler(self._token_auth, ta_responder)
        self._testServer.add_url_handler(self._test_over,
                                         self.__test_over_responder)
        self._client_latch = self._testServer.add_wait_url(self._client_login)
        self._issue_latch = self._testServer.add_wait_url(self._issue_token)
        self._over_latch = self._testServer.add_wait_url(self._test_over)


    def run(self):
        self._testServer.run()


    def stop(self):
        self._testServer.stop()


    def wait_for_client_login(self, timeout=10):
        self._client_latch.wait(timeout)
        if not self._client_latch.is_set():
            raise error.TestError('Never hit ClientLogin endpoint.')


    def wait_for_issue_token(self, timeout=10):
        self._issue_latch.wait(timeout)
        if not self._issue_latch.is_set():
            raise error.TestError('Never hit IssueAuthToken endpoint.')


    def wait_for_test_over(self, timeout=10):
        self._over_latch.wait(timeout)
        if not self._over_latch.is_set():
            raise error.TestError('Never redirected to /webhp.')


    def __client_login_responder(self, handler, url_args):
        logging.info(url_args)
        handler.send_response(httplib.OK)
        handler.end_headers()
        handler.wfile.write('SID=%s\n' % self.sid)
        handler.wfile.write('LSID=%s\n' % self.lsid)


    def __issue_token_responder(self, handler, url_args):
        logging.info(url_args)
        if not (self.sid == url_args['SID'].value and
                self.lsid == url_args['LSID'].value):
            raise error.TestError('IssueAuthToken called with incorrect args')
        handler.send_response(httplib.OK)
        handler.end_headers()
        handler.wfile.write(self.token)


    def __token_auth_responder(self, handler, url_args):
        logging.info(url_args)
        if not self.token == url_args['auth'][0]:
            raise error.TestError('TokenAuth called with incorrect args')
        if not 'continue' in url_args:
            raise error.TestError('TokenAuth called with no continue param')
        handler.send_response(httplib.SEE_OTHER)
        handler.send_header('Location', url_args['continue'][0])
        handler.end_headers()


    def __test_over_responder(self, handler, url_args):
        handler.send_response(httplib.OK)
        handler.end_headers()
