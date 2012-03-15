# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob, logging, os, re, stat

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import pexpect


DEFAULT_BASELINE = 'baseline'

FINGERPRINT_RE = re.compile(r'Fingerprint \(SHA1\):\n\s+(\b[:\w]+)\b')
NSS_ISSUER_RE = re.compile(r'Object Token:(.+\b)\s+[CGA]*,[CGA]*,[CGA]*')

NSSCERTUTIL = '/usr/local/bin/nsscertutil'
NSSMODUTIL = '/usr/local/bin/nssmodutil'
OPENSSL = '/usr/bin/openssl'

# This glob pattern is coupled to the snprintf() format in
# get_cert_by_subject() in crypto/x509/by_dir.c in the openssl
# sources.  In theory the glob can catch files not created by that
# snprintf(); such file names probably shouldn't be allowed to exist
# anyway.
OPENSSL_CERT_GLOB = '/etc/ssl/certs/' + '[0-9a-f]' * 8 + '.*'


class security_RootCA(test.test):
    version = 1

    def get_baseline_sets(self, baseline_file):
        """Returns a dictionary of sets. The keys are the names of
           the ssl components and the values are the sets of fingerprints
           we expect to find in that component's Root CA list.
        """
        baselines = {'nss': set([]), 'openssl': set([])}
        baseline_file = open(os.path.join(self.bindir, baseline_file))
        for line in baseline_file:
            (lib, fingerprint) = line.rstrip().split()
            if lib == 'both':
                baselines['nss'].add(fingerprint)
                baselines['openssl'].add(fingerprint)
            else:
                baselines[lib].add(fingerprint)
        return baselines

    def get_nss_certs(self):
        """Returns the set of certificate fingerprints observed in nss."""
        tmpdir = self.tmpdir

        # Create new empty cert DB.
        child = pexpect.spawn('"%s" -N -d %s' % (NSSCERTUTIL, tmpdir))
        child.expect('Enter new password:')
        child.sendline('foo')
        child.expect('Re-enter password:')
        child.sendline('foo')
        child.close()

        # Add the certs found in the compiled NSS shlib to a new module in DB.
        cmd = ('"%s" -add testroots -libfile %s -dbdir %s' %
               (NSSMODUTIL, glob.glob('/usr/lib*/libnssckbi.so')[0], tmpdir))
        nssmodutil = pexpect.spawn(cmd)
        nssmodutil.expect('\'q <enter>\' to abort, or <enter> to continue:')
        nssmodutil.sendline('\n')
        ret = utils.system_output(NSSMODUTIL + ' -list '
                                  '-dbdir %s' % tmpdir)
        self.assert_('2. testroots' in ret)

        # Dump out the list of root certs.
        all_certs = utils.system_output(NSSCERTUTIL +
                                        ' -L -d %s -h all' % tmpdir)
        certdict = {}  # A map of {SHA1_Fingerprint : CA_Nickname}.
        for cert in NSS_ISSUER_RE.findall(all_certs):
            cert_dump = utils.system_output(NSSCERTUTIL +
                                            ' -L -d %s -n '
                                            '\"Builtin Object Token:%s\"' %
                                            (tmpdir, cert))
            f = FINGERPRINT_RE.search(cert_dump)
            certdict[f.group(1)] = cert
        return set(certdict)


    def get_openssl_certs(self):
        """Returns the set of certificate fingerprints observed in openssl."""
        fingerprint_cmd = ' '.join([OPENSSL, 'x509', '-fingerprint',
                                    '-issuer', '-noout',
                                    '-in %s'])
        certdict = {}  # A map of {SHA1_Fingerprint : CA_Nickname}.

        for certfile in glob.glob(OPENSSL_CERT_GLOB):
            f, i = utils.system_output(fingerprint_cmd % certfile).splitlines()
            fingerprint = f.split('=')[1]
            for field in i.split('/'):
                items = field.split('=')
                # Compensate for stupidly malformed issuer fields.
                if len(items) > 1:
                    if items[0] == 'CN':
                        certdict[fingerprint] = items[1]
                        break
                    elif items[0] == 'O':
                        certdict[fingerprint] = items[1]
                        break
                else:
                    logging.warning('Malformed issuer string %s' % i)
            # Check that we found a name for this fingerprint.
            if not fingerprint in certdict:
                raise error.TestFail('Couldn\'t find issuer string for %s' %
                                     fingerprint)
        return set(certdict)


    def cert_perms_errors(self):
        """Returns True if certificate files have bad permissions."""
        # Acts as a regression check for crosbug.com/19848
        has_errors = False
        for certfile in glob.glob(OPENSSL_CERT_GLOB):
            s = os.stat(certfile)
            if s.st_uid != 0 or stat.S_IMODE(s.st_mode) != 0644:
                logging.error("Bad permissions: %s" %
                              utils.system_output("ls -lH %s" % certfile))
                has_errors = True

        return has_errors


    def run_once(self, opts=None):
        """Entry point for command line (run_remote_test) use. Accepts 2
           optional args, e.g. run_remote_test --args="relaxed baseline=foo".
           Parses the args array and invokes the main test method.
        """
        args = {'baseline': DEFAULT_BASELINE}
        if opts:
            args.update(dict([[k, v] for (k, e, v) in
                              [x.partition('=') for x in opts]]))

        self.verify_rootcas(baseline_file=args['baseline'],
                            exact_match=('relaxed' not in args))


    def verify_rootcas(self, baseline_file=DEFAULT_BASELINE, exact_match=True):
        """Verify installed Root CA's all appear on a specified whitelist.
           Covers both nss and openssl.
        """
        testfail = False

        # Dump certificate info and run comparisons.
        seen = {}
        seen['nss'] = self.get_nss_certs()
        seen['openssl'] = self.get_openssl_certs()
        expected = self.get_baseline_sets(baseline_file)

        for lib in seen.keys():
            missing = expected[lib].difference(seen[lib])
            unexpected = seen[lib].difference(expected[lib])
            if unexpected or (missing and exact_match):
                testfail = True
                logging.error('Results for %s' % lib)
                logging.error('Unexpected')
                for i in unexpected:
                    logging.error(i)
                if exact_match:
                    logging.error('Missing')
                    for i in missing:
                        logging.error(i)

        # cert_perms_errors() call first to avoid short-circuiting.
        # Short circuiting could mask additional failures that would
        # require a second build/test iteration to uncover.
        if self.cert_perms_errors() or testfail:
            raise error.TestFail('Unexpected Root CA findings')
