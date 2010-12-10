# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import auth_server, ui_test

class login_SecondFactor(ui_test.UITest):
    version = 1

    auto_login = False

    def __login_denier(self, handler, url_args):
        handler.send_response(403)
        handler.end_headers()
        handler.wfile.write('Error=BadAuthentication\n')
        handler.wfile.write('Info=InvalidSecondFactor')


    def start_authserver(self):
        self._authServer = auth_server.GoogleAuthServer(
            cl_responder=self.__login_denier)
        self._authServer.run()
        self.use_local_dns()


    def run_once(self):
        pass
