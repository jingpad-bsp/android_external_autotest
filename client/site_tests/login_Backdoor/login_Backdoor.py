# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import shutil, utils
from autotest_lib.client.cros import cros_ui_test, auth_server

class login_Backdoor(cros_ui_test.UITest):
    version = 1


    def __login_denier(self, handler, url_args):
        handler.send_response(403)
        handler.end_headers()
        handler.wfile.write('Error=BadAuthentication.')


    def start_authserver(self):
        self._authServer = auth_server.GoogleAuthServer(
            cl_responder=self.__login_denier)
        self._authServer.run()

        self.use_local_dns()


    def run_once(self):
        pass
