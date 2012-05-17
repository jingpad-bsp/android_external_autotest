# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

OPENSSL = '/usr/bin/openssl'
VERIFY = OPENSSL + ' verify'

class security_OpenSSLBlacklist(test.test):
    version = 1

    def verify(self, blacklist='/dev/null'):
        r = os.system('OPENSSL_BLACKLIST_PATH=%s %s -CAfile %s %s' %
            (blacklist, VERIFY, self.ca, self.cert))
        return r == 0

    def run_once(self, opts=None):
        self.hash_blacklist = '%s/hash_blacklist' % self.srcdir
        self.serial_blacklist = '%s/serial_blacklist' % self.srcdir
        self.bogus_blacklist = '%s/bogus_blacklist' % self.srcdir
        self.ca = '%s/ca.pem' % self.srcdir
        self.cert = '%s/cert.pem' % self.srcdir

        if not self.verify():
            raise error.TestFail('Certificate does not verify normally.')
        if self.verify(blacklist=self.hash_blacklist):
            raise error.TestFail('Certificate verified when blacklisted by hash.')
        if self.verify(blacklist=self.serial_blacklist):
            raise error.TestFail('Certificate verified when blacklisted by serial.')
        if not self.verify(blacklist=self.bogus_blacklist):
            raise error.TestFail('Certificate does not verify with nonempty blacklist.')
