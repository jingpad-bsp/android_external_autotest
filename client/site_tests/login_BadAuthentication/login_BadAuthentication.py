# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import auth_server, cros_ui_test, dns_server
from autotest_lib.client.cros import login

class login_BadAuthentication(cros_ui_test.UITest):
    version = 1

    auto_login = False


    def __authenticator(self, email, password):
        return False


    def initialize(self, creds='$default'):
        super(login_BadAuthentication, self).initialize(creds)


    def start_authserver(self):
        self._authServer = auth_server.GoogleAuthServer(
            authenticator=self.__authenticator)
        self._authServer.run()
        self._dnsServer = dns_server.LocalDns()
        self._dnsServer.run()


    def run_once(self):
        # Wrong password leads to automation timeout (45 secs). Fail sooner.
        timeout_reducer = self.pyauto.ActionTimeoutChanger(
            self.pyauto, 5000)  # 5 secs
        try:
            self.login(self.username, self.password)
        # TODO(craigdh): Find better way to determine login has failed (WebUI).
        except:
            pass
        else:
            raise error.TestFail('Should not have logged in')
        self._authServer.wait_for_service_login()
