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

    def veth(self, *args):
        self.callproc('/usr/local/lib/flimflam/test/veth', *args)

    def run(self, test):
        oldpid = self.callproc('pgrep', 'flimflamd').replace("\n", ' ')
        self.callproc('chmod', '755', self.bindir)
        self.callproc('chmod', '755', self.srcdir)
        self.callproc('chmod', '755', '%s/%s' % (self.srcdir, 'common.py'))
        self.callproc('chmod', '755', '%s/%s' % (self.srcdir, test))
        proc = subprocess.Popen(['/sbin/minijail', '--uid=210', '--gid=210',
                                 '/usr/bin/env', 'python', '%s/%s' % (self.srcdir, test)],
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
        cromo_was_running = True
        try:
            self.callproc('initctl', 'stop', 'cromo')
        except RuntimeError:
            cromo_was_running = False
            # It's okay if cromo's not running beforehand.
            pass
        time.sleep(3)
        try:
            for t in tests:
                try:
                    self.veth('setup', 'pseudo-modem0', '172.16.1')
                    self.run(t)
                finally:
                    self.veth('teardown', 'pseudo-modem0')
        finally:
            if cromo_was_running:
                self.callproc('initctl', 'start', 'cromo')
