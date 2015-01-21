# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import service_stopper

class graphics_SyncControlTest(test.test):
    """Confirms that infrastructure for aligning graphics operations in the
    browser with vsync is present
    """
    version = 1

    def setup(self):
        self.job.setup_dep(['glbench'])

    def run_once(self):
        if utils.is_freon():
            return
        dep = 'glbench'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)

        # TODO: I bet this list of boards is incomplete.
        #       Is there a better way to do this?
        hz = {'daisy' : 59.9}

        cmd = os.path.join(self.autodir, 'deps/glbench/synccontroltest')
        board = utils.get_current_board()
        if board in hz:
            cmd = cmd + " --vsync {0:.2f}".format(hz[board])
        cmd = 'X :1 vt1 & sleep 1; chvt 1 && DISPLAY=:1 ' + cmd

        self._services = service_stopper.ServiceStopper(['ui'])
        self._services.stop_services()

        try:
            # synccontroltest exits with a non zero status if a deviation above
            # 200uS us is detected.  utils.run will then raise an exception.
            utils.run(cmd, stderr_is_expected = False)
        finally:
            # Just sending SIGTERM to X is not enough; we must wait for it to
            # really die before we start a new X server (ie start ui).
            utils.ensure_processes_are_dead_by_name('^X$')

    def cleanup(self):
        if hasattr(self, '_services') and self._services:
            self._services.restore_services()
