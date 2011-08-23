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

    def _exists_on_client(self, f):
        return self.client.run('ls "%s"' % f,
                               ignore_status=True).exit_status == 0

    def _enable_consent(self):
        """ Enable consent so that crashes get stored in /var/spool/crash. """
        self._consent_files = [
            (CrashTestDefs._PAUSE_FILE, None, 'chronos'),
            (CrashTestDefs._CONSENT_FILE, None, 'chronos'),
            (CrashTestDefs._POLICY_FILE, 'mock_metrics_on.policy', 'root'),
            (CrashTestDefs._OWNER_KEY_FILE, 'mock_metrics_owner.key', 'root'),
            ]
        for dst, src, owner in self._consent_files:
            if self._exists_on_client(dst):
                self.client.run('mv "%s" "%s.autotest_backup"' % (dst, dst))
            if src:
                full_src = os.path.join(self.autodir, 'client/cros', src)
                self.client.send_file(full_src, dst)
            else:
                self.client.run('touch "%s"' % dst)
            self.client.run('chown "%s" "%s"' % (owner, dst))

    def _restore_consent_files(self):
        """ Restore consent files to their previous values. """
        for f, _, _ in self._consent_files:
            self.client.run('rm -f "%s"' % f)
            if self._exists_on_client('%s.autotest_backup' % f):
                self.client.run('mv "%s.autotest_backup" "%s"' % (f, f))

    def cleanup(self):
        self._restore_consent_files()
        test.test.cleanup(self)

    def run_once(self, host=None):
        self.client = host
        self._enable_consent()

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
            self.client.wait_for_restart(
                down_timeout=timeout,
                down_warning=timeout,
                old_boot_id=boot_id,
                # Double the default reboot timeout as some targets take longer
                # than normal before ssh is available again.
                timeout=self.client.DEFAULT_REBOOT_TIMEOUT * 4)
            result = self.client.run('cat %s/kernel.*.kcrash' % crash_log_dir)
            if text not in result.stdout:
                raise error.TestFail(
                    "No '%s' in the log after sending '%s'" % (text, action))
