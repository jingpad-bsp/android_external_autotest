# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import pwd
import stat

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import constants, cros_ui_test, cryptohome, login


class security_ProfilePermissions(cros_ui_test.UITest):
    version = 2
    _HOMEDIR_MODE = 0700

    def check_owner_mode(self, path, expected_owner, expected_mode):
        """
        Checks if the file/directory at 'path' is owned by 'expected_owner'
        with permissions matching 'expected_mode'.
        Returns True if they match, else False.
        Logs any mismatches to logging.error.
        """
        s = os.stat(path)
        actual_owner = pwd.getpwuid(s.st_uid).pw_name
        actual_mode = stat.S_IMODE(s.st_mode)
        if (expected_owner != actual_owner or
            expected_mode != actual_mode):
            logging.error("%s - Expected %s:%s, saw %s:%s" %
                          (path, expected_owner, oct(expected_mode),
                           actual_owner, oct(actual_mode)))
            return False
        else:
            return True


    def run_once(self):
        """Check permissions within cryptohome for anything too permissive."""
        passes = []
        login.wait_for_initial_chrome_window()

        homepath = constants.CRYPTOHOME_MOUNT_PT
        homemode = stat.S_IMODE(os.stat(homepath)[stat.ST_MODE])

        if homemode != self._HOMEDIR_MODE:
            passes.append(False)
            logging.error('%s permissions were %s' % (homepath, oct(homemode)))

        # Writable by anyone else is bad, as is owned by anyone else.
        cmd = 'find -L "%s" \\( -perm /022 -o \\! -user chronos \\) -ls'
        cmd %= homepath
        cmd_output = utils.system_output(cmd, ignore_status=True)
        if cmd_output:
            passes.append(False)
            logging.error(cmd_output)

        # This next section only applies if we have a real vault mounted
        # (ie, not a BWSI tmpfs).
        if cryptohome.is_mounted():
            # Also check the permissions of the underlying vault and
            # supporting directory structure.
            vaultpath = cryptohome.current_mounted_vault()

            passes.append(self.check_owner_mode(vaultpath, "chronos", 0700))
            passes.append(self.check_owner_mode(vaultpath + "/../master.0",
                                                "root", 0600))
            passes.append(self.check_owner_mode(vaultpath + "/../",
                                                "root", 0700))
            passes.append(self.check_owner_mode(vaultpath + "/../../",
                                                "root", 0700))

        if False in passes:
            raise error.TestFail('Bad permissions found on cryptohome files')
