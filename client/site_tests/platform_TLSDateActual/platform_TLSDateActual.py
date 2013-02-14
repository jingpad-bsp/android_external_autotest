# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import subprocess
import test

class platform_TLSDateActual(test.test):
    version = 1

    def run_once(self):
        p = subprocess.Popen(['/usr/bin/tlsdate',
                              '-v', '-l', '-H', 'clients3.google.com'],
                             stderr=subprocess.PIPE)
        out = p.communicate()[1]
        print out
        if p.returncode != 0:
            raise error.TestFail('tlsdate exited with %d' % p.returncode)
