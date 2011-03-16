# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import stat

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import constants, cros_ui_test, login

class security_ProfilePermissions(cros_ui_test.UITest):
    version = 1
    _HOMEDIR_MODE = 040700
    auto_login = False
    username = None
    password = None

    def run_once(self, creds=None):
        """
        Check permissions within cryptohome for anything too permissive.
        """
        if creds:
            self.username = constants.CREDENTIALS[creds][0]
            self.password = constants.CREDENTIALS[creds][1]

        self.login(self.username, self.password)
        login.wait_for_initial_chrome_window()

        homepath = constants.CRYPTOHOME_MOUNT_PT
        homemode = os.stat(homepath)[stat.ST_MODE]

        if (homemode != self._HOMEDIR_MODE):
            raise error.TestFail('%s permissions were %s' % (homepath,
                                                             oct(homemode)))

        # Writable by anyone else is bad, as is owned by anyone else.
        cmd = 'find -L "%s" -perm /022 -o \\! -user chronos -ls' % homepath
        cmd_output = utils.system_output(cmd, ignore_status=True)

        if (cmd_output != '') :
            logging.error(cmd_output)
            raise error.TestFail('Bad permissions found on cryptohome files')
