# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import logging
import os.path

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import constants, cros_ui, login


class security_RestartJob(test.test):
    version = 1
    _FLAGFILE = '/tmp/security_RestartJob_regression'


    def _ps(self, proc=constants.BROWSER):
        pscmd = 'ps -C %s -o pid --no-header | head -1' % proc
        return utils.system_output(pscmd)


    def run_once(self):
        """Verifies that RestartJob cannot be abused to execute
        arbitrary processes.
        """
        login.wait_for_browser()
        bus = dbus.SystemBus()
        proxy = bus.get_object('org.chromium.SessionManager',
                               '/org/chromium/SessionManager')
        sessionmanager = dbus.Interface(proxy,
                                        'org.chromium.SessionManagerInterface')

        # We can't just start our own sacrificial process to let
        # 'session_manager' kill, because it knows which processes it's
        # managing, so we have to locate the pid of Chrome.
        pid = int(self._ps())

        # Craft a malicious replacement for the target process.
        cmd = 'touch %s' % self._FLAGFILE

        # Try to get our malicious replacement to run.
        logging.info('Calling RestartJob(%s, \'%s\')', pid, cmd)
        testfail = False
        try:
            if sessionmanager.RestartJob(pid, cmd):
                raise error.TestFail(
                        'RestartJob regression, see crbug.com/193322')
        except dbus.DBusException:
            pass

        testfail = os.path.exists(self._FLAGFILE)

        # Clean up before we throw TestFail, since this test killed Chrome.
        cros_ui.nuke()

        if testfail:
            raise error.TestFail('RestartJob regression, see crbug.com/189233')
