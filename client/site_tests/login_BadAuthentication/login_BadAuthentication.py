# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import site_login
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import auth_server, ui_test

class login_BadAuthentication(ui_test.UITest):
    version = 1

    auto_login = False

    _errorString = None

    def __login_denier(self, handler, url_args):
        handler.send_response(403)
        handler.end_headers()
        handler.wfile.write(self._errorString)


    def initialize(self, creds='$default'):
        super(login_BadAuthentication, self).initialize(creds)


    def start_authserver(self):
        self._authServer = auth_server.GoogleAuthServer(
            cl_responder=self.__login_denier)
        self._authServer.run()
        self.use_local_dns()


    def run_once(self, error_string='BadAuthentication'):
        self._errorString = "Error=" + error_string
        # TODO(cmasone): find better way to determine login has failed.
        try:
            self.login(self.username, self.password)
        except site_login.TimeoutError:
            pass
        else:
            raise error.TestFail('Should not have logged in')
        self._authServer.wait_for_client_login()
