# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import logging
import os.path
import subprocess

from autotest_lib.client.bin import chromeos_constants
from autotest_lib.client.bin import site_login, test, utils
from autotest_lib.client.common_lib import error


class security_RestartJob(test.test):
    version = 1
    _FLAGFILE = '/tmp/security_RestartJob_regression'

    def _ps(self, proc=chromeos_constants.BROWSER):
        pscmd = 'ps -C %s -o pid --no-header | head -1' % proc
        return utils.system_output(pscmd)

    def run_once(self):
        """
        Verifies that RestartJob cannot be abused to exec
        arbitrary processes.
        """
        site_login.wait_for_browser()
        bus = dbus.SystemBus()
        proxy = bus.get_object('org.chromium.SessionManager',
                               '/org/chromium/SessionManager')
        sessionmanager = dbus.Interface(proxy,
                           'org.chromium.SessionManagerInterface')

        # We can't just start our own sacrificial process to let
        # Session Manager kill, because it knows which processes it's
        # managing... So we have to locate the pid of chrome.
        pid = int(self._ps())

        # Craft a malicious replacement for the target process
        cmd = 'touch %s' % self._FLAGFILE

        # Try to get our malicious replacement to run
        logging.info('Calling RestartJob(%s,\'%s\')' % (pid,cmd))
        sessionmanager.RestartJob(pid, cmd)

        testfail = os.path.exists(self._FLAGFILE)

        # Clean up, before we throw our TestFail, since this test
        # killed chrome and mangled its argv...
        site_login.nuke_login_manager()

        if testfail:
            raise error.TestFail('RestartJob regression, see cros bug 7018')
