# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os.path

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import upstart


class platform_CUPSDaemon(test.test):
    """
    Runs some sanity tests for cupsd and the upstart-socket-bridge
    socket-activation.
    """
    version = 1

    _CUPS_SOCK_PATH = '/run/cups/cups.sock'


    def check_cups_is_responding(self):
        """
        Run a basic sanity test to be sure CUPS is operating.
        """

        # Try a simple CUPS command; timeout/fail if it takes too long (i.e.,
        # socket may exist, but it may not get passed off to cupsd propertly).
        utils.system_output('lpstat -W all', timeout=10)


    def run_once(self):
        """
        Run some sanity tests for cupsd and the upstart-socket-bridge
        socket-activation.
        """
        if not upstart.has_service('cupsd'):
            raise error.TestNAError('No cupsd service found')

        upstart.ensure_running('upstart-socket-bridge')

        if not os.path.exists(self._CUPS_SOCK_PATH):
            raise error.TestFail('Missing CUPS socket: %s', self._CUPS_SOCK_PATH)

        # Make sure CUPS is stopped, so we can test on-demand launch.
        if upstart.is_running('cupsd'):
            upstart.stop_job('cupsd')

        self.check_cups_is_responding()

        # Now try stopping socket bridge, to see it clean up its files.
        upstart.stop_job('upstart-socket-bridge')
        upstart.stop_job('cupsd')

        if os.path.exists(self._CUPS_SOCK_PATH):
            raise error.TestFail('CUPS socket was not cleaned up: %s', self._CUPS_SOCK_PATH)

        # Create dummy file, to see if upstart-socket-bridge will clear it out
        # properly.
        utils.system('touch %s' % self._CUPS_SOCK_PATH)

        upstart.restart_job('upstart-socket-bridge')

        if not os.path.exists(self._CUPS_SOCK_PATH):
            raise error.TestFail('Missing CUPS socket: %s', self._CUPS_SOCK_PATH)

        self.check_cups_is_responding()
