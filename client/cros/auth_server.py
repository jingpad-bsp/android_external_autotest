# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import httplib, json, logging, os, socket, stat, time, urllib

import common, constants, cryptohome, httpd
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error


def _value(url_arg_value):
    """Helper unifying the handling of GET and POST arguments."""
    try:
        return url_arg_value[0]
    except AttributeError:
        return url_arg_value.value


class GoogleAuthServer(object):
    """A mock Google accounts server that can be run in a separate thread
    during autotests. By default, it returns happy-signals, accepting any
    credentials.
    """

    sid = '1234'
    lsid = '5678'
    token = 'aaaa'

    __service_login_html = """
<HTML>
<HEAD>
<SCRIPT type='text/javascript' src='../service_login.js'></SCRIPT>
<SCRIPT>
function submitAndGo() {
  gaia.chromeOSLogin.onAttemptedLogin(document.getElementById("Email"),
                                      document.getElementById("Passwd"),
                                      document.getElementById("continue"));
  return true;
}
function onAuthError() {
  if (window.domAutomationController) {
    window.domAutomationController.sendWithId(4444, 'loginfail');
  }
}
function onLoad() {
  gaia.chromeOSLogin.clearOldAttempts();
  %(onload)s
}
</SCRIPT>
</HEAD>
<BODY onload='onLoad();'>
  Local Auth Server:<BR>
  <FORM action=%(form_url)s method=POST onsubmit='submitAndGo()'>
    <INPUT TYPE=text id="Email" name="Email">
    <INPUT TYPE=text id="Passwd" name="Passwd">
    <P>%(error_message)s</P>
    <INPUT TYPE=hidden id="continue" name="continue" value=%(continue)s>
    <INPUT TYPE=Submit id="signIn">
  </FORM>
</BODY>
</HTML>
    """
    __oauth1_request_token = 'oauth1_request_token'
    __oauth1_access_token = 'oauth1_access_token'
    __oauth1_access_token_secret = 'oauth1_access_token_secret'
    __oauth2_auth_code = 'oauth2_auth_code'
    __oauth2_refresh_token = 'oauth2_refresh_token'
    __oauth2_access_token = 'oauth2_access_token'
    __issue_auth_token_miss_count = 0
    __token_auth_miss_count = 0


    def __init__(self,
                 cert_path='/etc/fake_root_ca/mock_server.pem',
                 key_path='/etc/fake_root_ca/mock_server.key',
                 ssl_port=443,
                 port=80,
                 authenticator=None):
        self._service_login = constants.SERVICE_LOGIN_URL
        self._service_login_new = constants.SERVICE_LOGIN_NEW_URL
        self._service_login_auth = constants.SERVICE_LOGIN_AUTH_URL

        self._oauth1_get_request_token = constants.OAUTH1_GET_REQUEST_TOKEN_URL
        self._oauth1_get_request_token_new = \
            constants.OAUTH1_GET_REQUEST_TOKEN_NEW_URL
        self._oauth1_get_access_token = constants.OAUTH1_GET_ACCESS_TOKEN_URL
        self._oauth1_get_access_token_new = \
            constants.OAUTH1_GET_ACCESS_TOKEN_NEW_URL
        self._oauth1_login = constants.OAUTH1_LOGIN_URL
        self._oauth1_login_new = constants.OAUTH1_LOGIN_NEW_URL

        self._oauth2_wrap_bridge = constants.OAUTH2_WRAP_BRIDGE_URL
        self._oauth2_wrap_bridge_new = constants.OAUTH2_WRAP_BRIDGE_NEW_URL
        self._oauth2_get_auth_code = constants.OAUTH2_GET_AUTH_CODE_URL
        self._oauth2_get_token = constants.OAUTH2_GET_TOKEN_URL

        self._client_login = constants.CLIENT_LOGIN_URL
        self._client_login_new = constants.CLIENT_LOGIN_NEW_URL
        self._issue_token = constants.ISSUE_AUTH_TOKEN_URL
        self._issue_token_new = constants.ISSUE_AUTH_TOKEN_NEW_URL
        self._token_auth = constants.TOKEN_AUTH_URL
        self._token_auth_new = constants.TOKEN_AUTH_NEW_URL
        self._test_over = '/webhp'

        self._testServer = httpd.SecureHTTPListener(
            port=ssl_port,
            docroot=os.path.dirname(__file__),
            cert_path=cert_path,
            key_path=key_path)
        sa = self._testServer.getsockname()
        logging.info('Serving HTTPS on %s, port %s' % (sa[0], sa[1]))

        if authenticator is None:
            authenticator = self.authenticator
        self._authenticator = authenticator

        self._testServer.add_url_handler(self._service_login,
                                         self._service_login_responder)
        self._testServer.add_url_handler(self._service_login_new,
                                         self._service_login_responder)
        self._testServer.add_url_handler(self._service_login_auth,
                                         self._service_login_auth_responder)

        self._testServer.add_url_handler(
            self._oauth1_get_request_token,
            self._oauth1_get_request_token_responder)
        self._testServer.add_url_handler(
            self._oauth1_get_request_token_new,
            self._oauth1_get_request_token_responder)
        self._testServer.add_url_handler(
            self._oauth1_get_access_token,
            self._oauth1_get_access_token_responder)
        self._testServer.add_url_handler(
            self._oauth1_get_access_token_new,
            self._oauth1_get_access_token_responder)
        self._testServer.add_url_handler(self._oauth1_login,
                                         self._oauth1_login_responder)
        self._testServer.add_url_handler(self._oauth1_login_new,
                                         self._oauth1_login_responder)

        self._testServer.add_url_handler(self._oauth2_wrap_bridge,
                                         self._oauth2_wrap_bridge_responder)
        self._testServer.add_url_handler(self._oauth2_wrap_bridge_new,
                                         self._oauth2_wrap_bridge_responder)
        self._testServer.add_url_handler(self._oauth2_get_auth_code,
                                         self._oauth2_get_auth_code_responder)
        self._testServer.add_url_handler(self._oauth2_get_token,
                                         self._oauth2_get_token_responder)

        self._testServer.add_url_handler(self._client_login,
                                         self._client_login_responder)
        self._testServer.add_url_handler(self._client_login_new,
                                         self._client_login_responder)
        self._testServer.add_url_handler(self._issue_token,
                                         self._issue_token_responder)
        self._testServer.add_url_handler(self._issue_token_new,
                                         self._issue_token_responder)
        self._testServer.add_url_handler(self._token_auth,
                                         self._token_auth_responder)
        self._testServer.add_url_handler(self._token_auth_new,
                                         self._token_auth_responder)

        self._service_latch = self._testServer.add_wait_url(self._service_login)
        self._service_new_latch = self._testServer.add_wait_url(
            self._service_login_new)
        self._client_latch = self._testServer.add_wait_url(self._client_login)
        self._client_new_latch = self._testServer.add_wait_url(
            self._client_login_new)
        self._issue_latch = self._testServer.add_wait_url(self._issue_token)
        self._issue_new_latch = self._testServer.add_wait_url(
            self._issue_token_new)

        self._testHttpServer = httpd.HTTPListener(port=port)
        self._testHttpServer.add_url_handler(self._test_over,
                                             self.__test_over_responder)
        self._testHttpServer.add_url_handler(constants.PORTAL_CHECK_URL,
                                             self._portal_check_responder)
        self._over_latch = self._testHttpServer.add_wait_url(self._test_over)


    def run(self):
        self._testServer.run()
        self._testHttpServer.run()


    def stop(self):
        self._testServer.stop()
        self._testHttpServer.stop()


    def wait_for_service_login(self, timeout=10):
        self._service_new_latch.wait(timeout)
        if not self._service_new_latch.is_set():
            self._service_latch.wait(timeout)
            if not self._service_latch.is_set():
                raise error.TestError('Never hit ServiceLogin endpoint.')


    def wait_for_client_login(self, timeout=10):
        self._client_new_latch.wait(timeout)
        if not self._client_new_latch.is_set():
            self._client_latch.wait(timeout)
            if not self._client_latch.is_set():
                raise error.TestError('Never hit ClientLogin endpoint.')


    def wait_for_issue_token(self, timeout=10):
        self._issue_new_latch.wait(timeout)
        if not self._issue_new_latch.is_set():
            self._issue_latch.wait(timeout)
            if not self._issue_latch.is_set():
                self.__issue_auth_token_miss_count += 1
                logging.error('Never hit IssueAuthToken endpoint.')


    def wait_for_test_over(self, timeout=10):
        self._over_latch.wait(timeout)
        if not self._over_latch.is_set():
            self.__token_auth_miss_count += 1
            logging.error('Never redirected to /webhp.')


    def get_endpoint_misses(self):
        results = {}
        if (self.__issue_auth_token_miss_count > 0):
            results['issue_auth_token_miss'] =self.__issue_auth_token_miss_count
        if (self.__token_auth_miss_count > 0):
            results['token_auth_miss'] = self.__token_auth_miss_count
        return results


    def authenticator(self, email, password):
      return True


    def _ensure_params_provided(self, handler, url_args, params):
      for param in params:
            if not param in url_args:
                handler.send_response(httplib.FORBIDDEN)
                handler.end_headers()
                raise error.TestError(
                    '%s did not receive a %s param.' % (handler.path, param))


    def _return_login_form(self, handler, error_message, continue_url,
                           onload=''):
        handler.send_response(httplib.OK)
        handler.end_headers()
        handler.wfile.write(self.__service_login_html % {
            'form_url': self._service_login_auth,
            'error_message': error_message,
            'continue': continue_url,
            'onload': onload})


    def _log(self, handler, url_args):
        logging.debug('%s: %s' % (handler.path, url_args))


    def _service_login_responder(self, handler, url_args):
        self._log(handler, url_args)
        self._ensure_params_provided(handler, url_args, ['continue'])
        self._return_login_form(handler, '', _value(url_args['continue']))


    def _service_login_auth_responder(self, handler, url_args):
        self._log(handler, url_args)
        self._ensure_params_provided(handler,
                                     url_args,
                                     ['continue', 'Email', 'Passwd'])
        if self._authenticator(_value(url_args['Email']),
                               _value(url_args['Passwd'])):
            handler.send_response(httplib.SEE_OTHER)
            handler.send_header('Location', _value(url_args['continue']))
            handler.end_headers()
        else:
            self._return_login_form(handler,
                                    constants.SERVICE_LOGIN_AUTH_ERROR,
                                    _value(['continue']),
                                    'onAuthError();')


    def _oauth1_get_request_token_responder(self, handler, url_args):
        self._log(handler, url_args)
        self._ensure_params_provided(handler,
                                     url_args,
                                     ['scope', 'xoauth_display_name'])
        handler.send_response(httplib.OK)
        handler.send_header('Set-Cookie',
                            'oauth_token=%s; Path=%s; Secure; HttpOnly' %
                                (self.__oauth1_request_token, handler.path))
        handler.end_headers()


    def _ensure_oauth1_params_valid(self, handler, url_args, expected_token):
        self._ensure_params_provided(handler,
                                     url_args,
                                     ['oauth_consumer_key',
                                      'oauth_token',
                                      'oauth_signature_method',
                                      'oauth_signature',
                                      'oauth_timestamp',
                                      'oauth_nonce'])
        if not ('anonymous' == _value(url_args['oauth_consumer_key']) and
                expected_token == _value(url_args['oauth_token'])):
            raise error.TestError(
                '%s called with incorrect params.' % handler.path)


    def _oauth1_get_access_token_responder(self, handler, url_args):
        self._log(handler, url_args)
        self._ensure_oauth1_params_valid(handler,
                                         url_args,
                                         self.__oauth1_request_token)
        handler.send_response(httplib.OK)
        handler.send_header('Content-Type', 'application/x-www-form-urlencoded')
        handler.end_headers()
        handler.wfile.write(urllib.urlencode({
            'oauth_token': self.__oauth1_access_token,
            'oauth_token_secret': self.__oauth1_access_token_secret}))


    def _oauth1_login_responder(self, handler, url_args):
        self._log(handler, url_args)
        self._ensure_oauth1_params_valid(handler,
                                         url_args,
                                         self.__oauth1_access_token)
        handler.send_response(httplib.OK)
        handler.end_headers()
        handler.wfile.write('SID=%s\n' % self.sid)
        handler.wfile.write('LSID=%s\n' % self.lsid)
        handler.wfile.write('Auth=%s\n' % self.token)


    def _oauth2_wrap_bridge_responder(self, handler, url_args):
        self._log(handler, url_args)
        self._ensure_oauth1_params_valid(handler,
                                         url_args,
                                         self.__oauth1_access_token)
        handler.send_response(httplib.OK)
        handler.send_header('Content-Type', 'application/x-www-form-urlencoded')
        handler.end_headers()
        handler.wfile.write(urllib.urlencode({
            'wrap_access_token': self.__oauth2_access_token,
            'wrap_access_token_expires_in': '3600'}))


    def _ensure_oauth2_params_valid(self, handler, url_args):
        self._ensure_params_provided(handler, url_args, ['scope', 'client_id'])
        if constants.OAUTH2_CLIENT_ID != _value(url_args['client_id']):
            raise error.TestError(
                '%s called with incorrect params.' % handler.path)


    def _oauth2_get_auth_code_responder(self, handler, url_args):
        self._log(handler, url_args)
        self._ensure_oauth2_params_valid(handler, url_args)
        handler.send_response(httplib.OK)
        handler.send_header('Set-Cookie',
                            'oauth_code=%s; Path=%s; Secure; HttpOnly' %
                                (self.__oauth2_auth_code, handler.path))
        handler.end_headers()


    def _oauth2_get_token_responder(self, handler, url_args):
        self._log(handler, url_args)
        self._ensure_oauth2_params_valid(handler, url_args)
        self._ensure_params_provided(handler,
                                     url_args,
                                     ['grant_type', 'client_secret'])
        if constants.OAUTH2_CLIENT_SECRET != _value(url_args['client_secret']):
            raise error.TestError(
                '%s called with incorrect params.' % handler.path)
        if 'authorization_code' == _value(url_args['grant_type']):
            self._ensure_params_provided(handler, url_args, ['code'])
            if self.__oauth2_auth_code != _value(url_args['code']):
                raise error.TestError(
                    '%s called with incorrect params.' % handler.path)
        elif 'refresh_token' == _value(url_args['grant_type']):
            self._ensure_params_provided(handler, url_args, ['refresh_token'])
            if self.__oauth2_refresh_token != _value(url_args['refresh_token']):
                raise error.TestError(
                    '%s called with incorrect params.' % handler.path)
        else:
            raise error.TestError(
                '%s called with incorrect params.' % handler.path)
        handler.send_response(httplib.OK)
        handler.end_headers()
        handler.wfile.write(json.dumps({
            'refresh_token': self.__oauth2_refresh_token,
            'access_token': self.__oauth2_access_token,
            'expires_in': 3600}))


    def _client_login_responder(self, handler, url_args):
        self._log(handler, url_args)
        self._ensure_params_provided(handler, url_args, ['Email', 'Passwd'])
        if self._authenticator(_value(url_args['Email']),
                               _value(url_args['Passwd'])):
            handler.send_response(httplib.OK)
            handler.end_headers()
            handler.wfile.write('SID=%s\n' % self.sid)
            handler.wfile.write('LSID=%s\n' % self.lsid)
        else:
            handler.send_response(httplib.FORBIDDEN)
            handler.end_headers()
            handler.wfile.write('Error=BadAuthentication')


    def _issue_token_responder(self, handler, url_args):
        self._log(handler, url_args)
        self._ensure_params_provided(handler,
                                     url_args,
                                     ['service', 'SID', 'LSID'])
        if not (self.sid == _value(url_args['SID']) and
                self.lsid == _value(url_args['LSID'])):
            raise error.TestError(
                '%s called with incorrect params.' % handler.path)
        # Block Chrome sync as we do not currently mock the server for it.
        if _value(url_args['service']) in ['chromiumsync', 'mobilesync']:
            handler.send_response(httplib.FORBIDDEN)
            handler.end_headers()
            handler.wfile.write('Error=ServiceUnavailable')
        else:
            handler.send_response(httplib.OK)
            handler.end_headers()
            handler.wfile.write(self.token)


    def _token_auth_responder(self, handler, url_args):
        self._log(handler, url_args)
        self._ensure_params_provided(handler, url_args, ['auth', 'continue'])
        if not self.token == _value(url_args['auth']):
            raise error.TestError(
                '%s called with incorrect param.' % handler.path)
        handler.send_response(httplib.SEE_OTHER)
        handler.send_header('Location', _value(url_args['continue']))
        handler.end_headers()


    def _portal_check_responder(self, handler, url_args):
        logging.debug('Handling captive portal check.')
        handler.send_response(httplib.NO_CONTENT)
        handler.end_headers()


    def __test_over_responder(self, handler, url_args):
        handler.send_response(httplib.OK)
        handler.end_headers()
