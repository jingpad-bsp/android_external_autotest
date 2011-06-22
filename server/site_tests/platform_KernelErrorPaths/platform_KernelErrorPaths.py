# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.crash_test import CrashTest as CrashTestDefs
from autotest_lib.server import test

class platform_KernelErrorPaths(test.test):
    version = 1

    def breakme(self, text):
        # This test is ensuring that the machine will reboot on any
        # tyoe of kernel panic.  If the sysctls below are not set
        # correctly, the machine will not reboot.  After verifying
        # that the machine has the proper sysctl state, we make it
        # reboot by writing to a /proc/breakme.
        #
        # 2011.03.09: ARM machines will currently fail due to
        #             'preserved RAM' not being enabled.
        self.client.run('sysctl kernel.panic|grep "kernel.panic = -1"');
        self.client.run('sysctl kernel.panic_on_oops|'
                        'grep "kernel.panic_on_oops = 1"');

        command = "echo %s > /proc/breakme" % text
        logging.info("KernelErrorPaths: executing '%s' on %s" %
                     (command, self.client.hostname))
        try:
            # Simple sending text into /proc/breakme resets the target
            # immediately, leaving files unsaved to disk and the master ssh
            # connection wedged for a long time. The sequence below borrowed
            # from logging_KernelCrashServer.py makes sure that the test
            # proceeds smoothly.
            self.client.run(
                'sh -c "sync; sleep 1; %s" >/dev/null 2>&1 &' % command)
        except error.AutoservRunError, e:
            # It is expected that this will cause a non-zero exit status.
            pass

    def configure_crash_reporting(self):
        self._preserved_files = []
        for f in (CrashTestDefs._PAUSE_FILE, CrashTestDefs._CONSENT_FILE):
            if not os.path.exists(f):
                self.client.run('touch "%s"' % f)
                self.client.run('chown chronos "%s"' % f)
                self._preserved_files.append(f)

    def cleanup(self):
        for f in self._preserved_files:
            self.client.run('rm -f "%s"' % f)
        test.test.cleanup(self)

    def run_once(self, host=None):
        self.client = host
        self.configure_crash_reporting()

        crash_log_dir = CrashTestDefs._SYSTEM_CRASH_DIR

        # Each tuple consists of two strings: the 'breakme' string to send
        # into /proc/breakme on the target, and the crash report string to
        # look for in the crash dump after target restarts.
        # TODO(vbendeb): add the following breakme strings after fixing kernel
        # bugs:
        # 'deadlock' (has to be sent twice), 'softlockup', 'irqlockup'
        test_tuples = (
            ('softlockup', 'BUG: soft lockup', 25),
            ('bug', 'kernel BUG at', 10),
            ('hungtask', 'hung_task: blocked tasks', 250),
            ('nmiwatchdog', 'Watchdog detected hard LOCKUP', 15),
            ('nullptr',
             'BUG: unable to handle kernel NULL pointer dereference at', 10),
            ('panic', 'Kernel panic - not syncing:', 10),
            )

        for action, text, timeout in test_tuples:
            # Delete crash results, if any
            self.client.run('rm -f %s/*' % crash_log_dir)
            boot_id = self.client.get_boot_id()
            self.breakme(action)  # This should cause target reset.
            self.client.wait_for_restart(down_timeout=timeout,
                                         old_boot_id=boot_id)
            result = self.client.run('cat %s/kernel.*.kcrash' % crash_log_dir)
            if text not in result.stdout:
                raise error.TestFail(
                    "No '%s' in the log after sending '%s'" % (text, action))
