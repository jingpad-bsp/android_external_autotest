# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import time

from autotest_lib.client.cros import cros_ui_test, httpd


class desktopui_SimpleLogin(cros_ui_test.UITest):
    version = 1


    def initialize(self):
        super(desktopui_SimpleLogin, self).initialize(creds='$default')
        self._testServer = httpd.HTTPListener(8000, docroot=self.bindir)
        self._testServer.run()


    def run_once(self):
        terminate_path = '/tmp/simple_login_exit'
        if os.path.isfile(terminate_path):
            os.remove(terminate_path)

        while True:
            time.sleep(1)
            if os.path.isfile(terminate_path):
                logging.info('Exit flag detected, exiting.')
                return
