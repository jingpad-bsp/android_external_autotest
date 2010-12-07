# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import chromeos_constants
from autotest_lib.client.bin import site_cryptohome, site_ui_test
from autotest_lib.client.common_lib import error, site_auth_server

class login_CryptohomeIncognitoMounted(site_ui_test.UITest):
    version = 1


    def __login_denier(self, handler, url_args):
        handler.send_response(403)
        handler.end_headers()
        handler.wfile.write('Error=BadAuthentication.')


    def start_authserver(self):
        self._authServer = site_auth_server.GoogleAuthServer(
            cl_responder=self.__login_denier)
        self._authServer.run()

        self.use_local_dns()

    def run_once(self):
        if (site_cryptohome.is_mounted(allow_fail=True) or
            not site_cryptohome.is_mounted_on_tmpfs(
                     device=chromeos_constants.CRYPTOHOME_INCOGNITO)):
            raise error.TestFail('CryptohomeIsMountedOnTmpfs should return '
                                 'True.')
