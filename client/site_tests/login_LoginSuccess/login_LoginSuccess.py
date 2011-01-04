# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import auth_server, ui_test

class login_LoginSuccess(ui_test.UITest):
    version = 1

    def __creds_checker(self, handler, url_args):
        logging.debug('checking %s == %s' % (self.username,
                                             url_args['Email'].value))
        if (self.username != url_args['Email'].value):
            raise error.TestError('Incorrect creds passed to ClientLogin')
        self._authServer.client_login_responder(handler, url_args)


    def initialize(self, creds='$default'):
        super(login_LoginSuccess, self).initialize(creds)


    def start_authserver(self):
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
