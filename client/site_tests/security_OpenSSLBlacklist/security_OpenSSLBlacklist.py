# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import subprocess
import time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

OPENSSL = '/usr/bin/openssl'
VERIFY = OPENSSL + ' verify'

class security_OpenSSLBlacklist(test.test):
    version = 1

    def verify(self, blacklist='/dev/null'):
        r = os.system('OPENSSL_BLACKLIST_PATH=%s %s -CAfile %s %s' %
            (blacklist, VERIFY, self.ca, self.cert))
        return r == 0

    def fetch(self, blacklist='/dev/null'):
        r = os.system('OPENSSL_BLACKLIST_PATH=%s curl --cacert %s -o /dev/null '
                      'https://127.0.0.1:4433/' % (blacklist, self.ca))
        return r == 0

    def run_once(self, opts=None):
        self.hash_blacklist = '%s/hash_blacklist' % self.srcdir
        self.serial_blacklist = '%s/serial_blacklist' % self.srcdir
        self.bogus_blacklist = '%s/bogus_blacklist' % self.srcdir
        self.ca = '%s/ca.pem' % self.srcdir
        self.cert = '%s/cert.pem' % self.srcdir
        self.key = '%s/cert.key' % self.srcdir

        if not self.verify():
            raise error.TestFail('Certificate does not verify normally.')
        if self.verify(self.hash_blacklist):
            raise error.TestFail('Certificate verified when blacklisted by hash.')
        if self.verify(self.serial_blacklist):
            raise error.TestFail('Certificate verified when blacklisted by serial.')
        if not self.verify(self.bogus_blacklist):
            raise error.TestFail('Certificate does not verify with nonempty blacklist.')

        # Fire up an openssl s_server and have curl fetch from it
        server = subprocess.Popen([OPENSSL, 's_server', '-www',
                                   '-CAfile', self.ca, '-cert', self.cert,
                                   '-key', self.key, '-port', '4433'])
        try:
            # Need to wait for openssl to be ready to talk to us
            if not utils.poll_for_condition(self.fetch):
                raise error.TestFail('Fetch without blacklist fails.')
            if self.fetch(self.hash_blacklist):
                raise error.TestFail('Fetch with hash blacklisted succeeds.')
            if self.fetch(self.serial_blacklist):
                raise error.TestFail('Fetch with serial blacklisted succeeds.')
            if not self.fetch(self.bogus_blacklist):
                raise error.TestFail('Fetch with nonempty blacklist fails.')
        finally:
            server.terminate()
