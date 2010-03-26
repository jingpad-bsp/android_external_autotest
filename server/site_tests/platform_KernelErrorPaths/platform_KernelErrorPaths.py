# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, shutil
from autotest_lib.server import test, autotest
from autotest_lib.client.common_lib import error

class platform_KernelErrorPaths(test.test):
    version = 1

    def breakme(self, command):
        logging.info('KernelErrorPaths: causing %s on host %s' %
                     (command, self.client.hostname))
        try:
            self.client.run("echo %s > /proc/breakme" % command)
        except error.AutoservRunError, e:
            # it is expected that this will cause a non-zero exit status
            pass


    def test_bug(self):
        """
        Cause the target to log a kernel bug, and then check in the
        messages to make sure it did.
        """
        # Clear the messages so we can compare.
        self.client.run('dmesg -c')
        # Cause the client to report a kernel BUG.
        self.breakme('bug')
        # Now get messages and check to make sure it's in there.
        result = self.client.run('dmesg')
        marker = "Kernel BUG at"
        found = False
        for line in result.stdout.split('\n'):
            if line.find(marker) != -1:
                found = True
                break
        if not found:
            error.TestFail("Kernel BUG reporting not working.")


    def test_deadlock(self):
        # Cause the target to go into a deadlock (have to run it twice).
        self.breakme('deadlock')
        self.breakme('deadlock')


    def test_soft_lockup(self):
        # Cause the target to go into an infinite loop.
        self.breakme('softlockup')


    def test_irq_lockup(self):
        # Cause the target to go into a lockup with interrupts enabled.
        self.breakme('irqlockup')


    def test_no_irq_lockup(self):
        # Cause the target to go into a lockup with interrupts disabled.
        self.breakme('nmiwatchdog')


    def test_null_dereference(self):
        # Clear the messages so we can compare.
        self.client.run('dmesg -c')
        # Cause the target to dereference a null pointer.
        self.breakme('nullptr')
        # Now get messages and check to make sure it was noticed.
        result = self.client.run('dmesg')
        found = False
        marker = "BUG: unable to handle kernel NULL pointer dereference"
        for line in result.stdout.split('\n'):
            if line.find(marker) != -1:
                found = True
                break
        if not found:
            error.TestFail("Kernel NULL pointer dereference detection "
                           "not working.")


    def test_panic(self):
        # Cause the target to panic.
        self.breakme('panic')
        if not self.client.wait_down(timeout=30):
            error.TestFail("Kernel panic went unnoticed.")
        if not self.client.wait_up(timeout=40):
            error.TestFail("Kernel panic didn't cause successful reboot.")


    def run_once(self, host=None):
        self.client = host

        self.test_bug()
        # TODO: Fill in the tests for these.
        # self.test_deadlock()
        # self.test_soft_lockup()
        # self.test_irq_lockup()
        # self.test_no_irq_lockup()
        self.test_null_dereference()
        self.test_panic()
