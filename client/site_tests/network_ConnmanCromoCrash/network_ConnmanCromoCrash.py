# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
import os, subprocess, time

tests = [ 'crash-mm-0', 'crash-modem-0', 'crash-modem-1', 'crash-modem-2',
          'crash-modem-3', 'crash-modem-4', 'crash-modem-5', 'crash-modem-6',
          'fail-mm-0', 'fail-modem-0', 'fail-modem-1', 'fail-modem-2',
          'fail-modem-3', 'fail-modem-4', 'fail-modem-5', 'fail-modem-6',
          'timeout-modem-0' ]

class network_ConnmanCromoCrash(test.test):
    version = 1

    def callproc(self, *args):
        proc = subprocess.Popen(args, stdout=subprocess.PIPE)
        (out, err) = proc.communicate()
        if proc.returncode:
            raise RuntimeError('callproc %s failed: %d' % (args[0],
                               proc.returncode))
        return str(out)

    def run(self, test):
        oldpid = self.callproc('pgrep', 'flimflamd').replace("\n", ' ')
        proc = subprocess.Popen(['%s/%s' % (self.srcdir, test)],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        (out, err) = proc.communicate()
        if out:
            out = out.replace("\n", ' ')
        if err:
            err = err.replace("\n", ' ')
        if proc.returncode:
            raise RuntimeError('Subprocess %s failed: %d %s %s' % (
                               test, proc.returncode, out, err))
        time.sleep(2)
        newpid = self.callproc('pgrep', 'flimflamd').replace("\n", ' ')
        if newpid != oldpid:
            raise RuntimeError('Flimflam pid changed: %s != %s' % (
                               oldpid,newpid))

    def run_once(self):
        for t in tests:
            self.run(t)
