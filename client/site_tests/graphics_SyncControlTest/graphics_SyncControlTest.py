# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, re, time

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
        dep = 'glbench'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)

        hz = {'daisy' : 59.9}

        exefile = os.path.join(self.autodir, 'deps/glbench/synccontroltest')
        cmd = "DISPLAY=:1 " + exefile
        board = utils.get_current_board()
        if board in hz:
            cmd = cmd + " --vsync {0:.2f}".format(hz[board])

        self._services = service_stopper.ServiceStopper(['ui'])
        self._services.stop_services()
        x_summary = utils.system_output('X :1 & echo "XPID=$!"',
                                            ignore_status=True)
        self.x_pid = re.match(r"XPID=(\d+)", x_summary).group(0)
        time.sleep(1)

        # synccontroltest exits with a non zero status if a deviation above
        # 200uS us is detected.
        ret = utils.system(cmd, ignore_status=True)
        if ret != 0:
            raise error.TestFail(
                "Failed: graphics_SyncControlTest with {0}".format(ret))

    def cleanup(self):
        if self.x_pid:
            utils.system("kill {0}".format(self.x_pid), ignore_status=True)
        if self._services:
            self._services.restore_services()
