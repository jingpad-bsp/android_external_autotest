# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, utils
from autotest_lib.client.bin import site_login, test
from autotest_lib.client.common_lib import site_ui

class desktopui_IBusTest(test.test):
    version = 1
    preserve_srcdir = True

    def setup(self):
        self.job.setup_dep(['autox'])
        self.job.setup_dep(['ibusclient'])


    def run_once(self):
        logged_in = site_login.logged_in()
        if not logged_in:
            if not site_login.attempt_login(self, 'autox_script.json'):
                raise error.TestFail('Could not login')
        try:
            dep = 'ibusclient'
            dep_dir = os.path.join(self.autodir, 'deps', dep)
            self.job.install_pkg(dep, 'dep', dep_dir)

            exefile = os.path.join(self.autodir, 'deps/ibusclient/ibusclient')
            cmd = site_ui.xcommand_as('DISPLAY=:0 %s' % exefile, 'chronos')
            utils.system_output(cmd, retain_output=True)
        finally:
            # If we started logged out, log back out.
            if not logged_in:
                site_login.attempt_logout()
