# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import auth_server, cros_ui_test

class login_LoginSuccess(cros_ui_test.UITest):
    version = 1

    def __creds_checker(self, handler, url_args):
        """Validate credentials before responding positively to an auth attempt.

        This method gets installed as the auth server's client_login_responder.
        We double-check that the url_args['Email'] matches our username before
        calling the auth server's default client_login_responder()
        implementation.

        @param handler: Passed on as handler to GoogleAuthServer's
                client_login_responder() method.
        @param url_args: The arguments to check.
        @raises error.TestError: If the url_args email doesn't match our
                username.
        """
        logging.debug('checking %s == %s' % (self.username,
                                             url_args['Email'].value))
        if (self.username != url_args['Email'].value):
            raise error.TestError('Incorrect creds passed to ClientLogin')
        self._authServer.client_login_responder(handler, url_args)


    def initialize(self, creds='$default', **dargs):
        """Override superclass to provide a default value for the creds param.

        This is important for our class, since a creds of None (AKA "browse
        without signing in") don't make sense for a test that is checking that
        authentication works properly.

        @param creds: See cros_ui_test.UITest; For us, the default is
                '$default'.
        """
        assert creds, "Must use non-Guest creds for login_LoginSuccess test."
        super(login_LoginSuccess, self).initialize(creds, **dargs)


    def start_authserver(self):
        """Override superclass to pass our creds checker to the auth server."""
        self._authServer = auth_server.GoogleAuthServer(
            cl_responder=self.__creds_checker)
        self._authServer.run()
        self.use_local_dns()


    def ensure_login_complete(self):
        """Wait for login to complete, including cookie fetching."""
        self._authServer.wait_for_client_login()
        self._authServer.wait_for_issue_token()
        self._authServer.wait_for_test_over()


    def run_once(self):
        pass


    def cleanup(self):
        super(login_LoginSuccess, self).cleanup()
        self.write_perf_keyval(self.get_auth_endpoint_misses())
