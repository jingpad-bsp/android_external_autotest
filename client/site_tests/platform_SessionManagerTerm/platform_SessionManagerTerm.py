# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus, logging, os, time
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import constants, cros_logging, cryptohome, login

class platform_SessionManagerTerm(test.test):
    version = 1

    _testuser = 'cryptohometest@chromium.org'
    _testpass = 'testme'


    def initialize(self):
        cryptohome.remove_vault(self._testuser)
        cryptohome.mount_vault(self._testuser, self._testpass, create=True)
        super(platform_SessionManagerTerm, self).initialize()


    def run_once(self):
        log_reader = cros_logging.LogReader()
        log_reader.set_start_by_current()
        binary = constants.SESSION_MANAGER
        # Try to kill all running instances of the binary.
        try:
            utils.system('pkill -TERM %s' % binary)
        except error.CmdError, e:
            logging.debug(e)
            raise error.TestFail('%s is not running before kill' % binary)

        # Check if the binary is running again (using os.system(), since it
        # doesn't raise an exception if the command fails).
        utils.poll_for_condition(
            lambda: os.system('pgrep %s' % binary) == 0,
            error.TestFail('%s is probably not running after TERM' % binary),
            timeout=20)
        # Assuming the process came back, did it exit appropriately?
        if not log_reader.can_find('SessionManagerService exiting'):
            error.TestFail('%s did not exit cleanly' % binary)


    def cleanup(self):
        cryptohome.unmount_vault()
        super(platform_SessionManagerTerm, self).cleanup()
