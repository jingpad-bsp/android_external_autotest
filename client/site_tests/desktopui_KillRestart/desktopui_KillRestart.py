# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, time
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class desktopui_KillRestart(test.test):
    version = 1

    def run_once(self, binary = 'chrome'):
        # Ensure the binary is running.
        utils.poll_for_condition(
            lambda: os.system('pgrep %s >/dev/null' % binary) == 0,
            error.TestFail('%s is not running at start of test' % binary),
            timeout=60)

        # Try to kill all running instances of the binary.
        try:
            utils.system('pkill -KILL %s' % binary)
        except error.CmdError, e:
            logging.debug(e)
            raise error.TestFail('%s is not running before kill' % binary)

        # Check if the binary is running again (using os.system(), since it
        # doesn't raise an exception if the command fails).
        utils.poll_for_condition(
            lambda: os.system('pgrep %s >/dev/null' % binary) == 0,
            error.TestFail('%s is not running after kill' % binary),
            timeout=60)
