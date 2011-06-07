# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


OPENSSL = '/usr/bin/openssl'
VERIFY = OPENSSL + ' verify'
BLACKLIST = '/etc/ssl/blacklist'

class security_OpenSSLBlacklist(test.test):
    version = 1

    def blacklist(self, fingerprint):
        f = open(BLACKLIST, 'a+')
        f.write('%s\n' % fingerprint)

    def unblacklist(self, fingerprint):
        with open(BLACKLIST, 'r') as f:
            lines = f.readlines()
            lines = [x.strip() for x in lines]
            lines = [x for x in lines if x != fingerprint]
        for line in lines:
            print "'%s' != '%s'" % (line, fingerprint)
        with open(BLACKLIST, 'w') as f:
            f.writelines(lines)

    def verify(self):
        r = os.system('%s -CAfile %s %s' % (VERIFY, self.ca, self.cert))
        return r == 0

    def run_once(self, opts=None):
        self.ca = '%s/ca.pem' % self.srcdir
        self.cert = '%s/cert.pem' % self.srcdir
        # This fingerprint comes from 'openssl x509 -in foo.pem -fingerprint -sha256'
        self.certfp = 'f641c36cfef49bc071359ecf88eed9317b738b5989416ad401720c0a4e2e6352'
        # ... and this one comes from 'head -c 16 /dev/urandom | sha256sum' :)
        self.bogus_certfp = 'bb708578662b7202b7ac3f420013a8a765e0b8687109a2cbba2b5a625358788f'

        try:
            os.system('mv %s %s.old' % (BLACKLIST, BLACKLIST))
            os.system('touch %s' % BLACKLIST)
            if not self.verify():
                raise error.TestFail('Certificate does not verify normally.')
            self.blacklist(self.certfp)
            if self.verify():
                raise error.TestFail('Certificate verified when blacklisted.')
            self.unblacklist(self.certfp)
            if not self.verify():
                raise error.TestFail('Certificate does not verify when unblacklisted.')
            self.blacklist(self.bogus_certfp)
            if not self.verify():
                raise error.TestFail('Certificate does not verify with nonempty blacklist.')
        finally:
            os.system('mv %s.old %s' % (BLACKLIST, BLACKLIST))
