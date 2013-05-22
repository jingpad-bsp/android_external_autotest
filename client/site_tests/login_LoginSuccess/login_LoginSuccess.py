# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import auth_server, cros_ui_test, dns_server

class login_LoginSuccess(cros_ui_test.UITest):
    version = 1


    def __authenticator(self, email, password):
        """Validate credentials before responding positively to an auth attempt.
        """
        logging.debug('checking %s == %s' % (self.username, email))
        if self.username != email:
            raise error.TestError('Incorrect creds passed to login handler.')
        return self.username == email


    def initialize(self, creds='$default'):
        """Override superclass to provide a default value for the creds param.

        This is important for our class, since a creds of None (AKA "browse
        without signing in") don't make sense for a test that is checking that
        authentication works properly.

        @param creds: See cros_ui_test.UITest; For us, the default is
                '$default'.
        """
        assert creds, "Must use non-Guest creds for login_LoginSuccess test."
        super(login_LoginSuccess, self).initialize(creds)


    def start_authserver(self):
        """Override superclass to use our authenticator."""
        super(login_LoginSuccess, self).start_authserver(
            authenticator=self.__authenticator)


    def ensure_login_complete(self):
        """Wait for login to complete, including cookie fetching."""
        self._authServer.wait_for_service_login()
        self._authServer.wait_for_issue_token()
        self._authServer.wait_for_test_over()


    def run_once(self):
        self.job.set_state('client_success', True)



    def cleanup(self):
        super(login_LoginSuccess, self).cleanup()
        self.write_perf_keyval(self.get_auth_endpoint_misses())
