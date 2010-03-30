# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, time, utils
from autotest_lib.client.bin import site_utils, test
from autotest_lib.client.common_lib import error

class desktopui_KillRestart(test.test):
    version = 1

    def run_once(self, binary = 'chrome'):
        # Try to kill all running instances of the binary.
        try:
            utils.system('pkill -KILL %s' % binary)
        except error.CmdError, e:
            logging.debug(e)
            raise error.TestFail('%s is not running before kill' % binary)

        # Check if the binary is running again (using os.system(), since it
        # doesn't raise an exception if the command fails).
        site_utils.poll_for_condition(
            lambda: os.system('pgrep %s' % binary) == 0,
            error.TestFail('%s is not running after kill' % binary))
