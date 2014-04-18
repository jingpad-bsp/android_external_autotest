# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import httplib
import os
import re
import stat
import subprocess

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import constants, httpd
from autotest_lib.client.cros.recall import RecallServer

class test_Recall(test.test):
    version = 1

    _certificate = """\
-----BEGIN CERTIFICATE-----
MIICejCCAeOgAwIBAgIJAJAMlNbcSCFeMA0GCSqGSIb3DQEBBQUAMDMxDzANBgNV
BAoTBkdvb2dsZTEgMB4GA1UECxMXQ2hyb21pdW0gT1MgVGVzdCBTZXJ2ZXIwHhcN
MTExMTEwMTk0NTQ0WhcNMTExMTExMTk0NTQ0WjAzMQ8wDQYDVQQKEwZHb29nbGUx
IDAeBgNVBAsTF0Nocm9taXVtIE9TIFRlc3QgU2VydmVyMIGfMA0GCSqGSIb3DQEB
AQUAA4GNADCBiQKBgQCc+gTR3R/OiY+AtZCsRI3CtHr+/7q8VRuci/rJU1R58OrX
qEPZx/rck1fpAA3rpCkfv/T7tXbmzyTVJ8cPh9scC22hM8OKppZeZSlX2hA8uocW
iheMkuUHcP+ya4z02GXNgUdLUiWSBfyme3cdHc5+Ugp1wrAOUkLG0Ya2x01I0QID
AQABo4GVMIGSMB0GA1UdDgQWBBQtD9gOLzc5O9aW+74nZL/VGQHRDDBjBgNVHSME
XDBagBQtD9gOLzc5O9aW+74nZL/VGQHRDKE3pDUwMzEPMA0GA1UEChMGR29vZ2xl
MSAwHgYDVQQLExdDaHJvbWl1bSBPUyBUZXN0IFNlcnZlcoIJAJAMlNbcSCFeMAwG
A1UdEwQFMAMBAf8wDQYJKoZIhvcNAQEFBQADgYEACNNJsaj/lMlmbu+tQe67GUwl
Cy68yHMFUmY6B2jBBhQLQlCVvB1HF3Tg0YGy9+OFBx00N2ysPRNhcuE2Hwv0mM4C
UMfRd7zhQDCEKDqqsJFOOrgu/MJKo3qkJBoreE4lmlnrIyhYpkN1TwAz4jVUCklV
7ZKxlI+3hii+ifNCPdU=
-----END CERTIFICATE-----
"""

    def _respond_with_certificate(self, handler, url_args):
        self._requested_certificate = True

        handler.send_response(httplib.OK)
        handler.send_header('Content-Type', 'text/plain')
        handler.send_header('Content-Length', str(len(self._certificate)))
        handler.end_headers()
        handler.wfile.write(self._certificate)
        handler.wfile.flush()

    def initialize(self):
        # Start a local web server (for the certificate fetch)
        self._listener = httpd.HTTPListener(80, docroot=self.srcdir)
        self._listener.add_url_handler('/GetRootCertificate',
                                       self._respond_with_certificate)
        self._listener.run()

    def run_once(self):
        self._requested_certificate = False

        # Get the current state of things
        orig_stat = os.stat(constants.FAKE_ROOT_CA_DIR)
        orig_resolv = open(constants.RESOLV_CONF_FILE).read()

        cmd = ( 'ip', 'route', 'show' )
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        orig_routing_table, errdata = proc.communicate()
        if proc.returncode != 0:
            raise error.TestFail('Could not retrieve routing table')

        # Run the test with the recall wrapper
        with RecallServer('127.0.0.1'):
            # Certificate much have been fetched from our http server
            if not self._requested_certificate:
                raise error.TestFail('Never requested certificate.')

            # tmpfs must have been mounted over the root ca directory
            test_stat = os.stat(constants.FAKE_ROOT_CA_DIR)
            if (test_stat.st_ino, test_stat.st_dev) \
                    == (orig_stat.st_ino, orig_stat.st_dev):
                raise error.TestFail('Did not mount tmpfs over %s',
                                     constants.FAKE_ROOT_CA_DIR)

            # Certificate must be in the nssdb
            cmd = ( 'certutil', '-d', 'sql:' + constants.FAKE_NSSDB_DIR,
                    '-L', '-a', '-n', 'Chromium OS Test Server' )
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            data, errdata = proc.communicate()
            if proc.returncode != 0:
                raise error.TestFail('Did not find certificate in nssdb')
            if data.replace('\r', '') != self._certificate:
                raise error.TestFail('Incorrect certificate in nssdb')

            # DNS server must be changed to our IP
            if open('/etc/resolv.conf').read() != 'nameserver 127.0.0.1\n':
                raise error.TestFail('Nameserver not changed')

            # Default route must have been changed
            cmd = ( 'ip', 'route', 'show' )
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            data, errdata = proc.communicate()
            if proc.returncode != 0:
                raise error.TestFail('Could not retrieve routing table')
            for line in data.splitlines():
                if not line.startswith("default "):
                    continue
                match = re.search(r'via ([^ ]*)', line)
                if not match:
                    continue
                if match.group(1) != '127.0.0.1':
                    raise error.TestFail('Default route gateway not changed')
                break
            else:
                raise error.TestFail('No default route found')

        # Mounted tmpfs must have been unmounted again
        test_stat = os.stat(constants.FAKE_ROOT_CA_DIR)
        if (test_stat.st_ino, test_stat.st_dev) \
                != (orig_stat.st_ino, orig_stat.st_dev):
            raise error.TestFail('Did not unmount tmpfs from %s',
                                  constants.FAKE_ROOT_CA_DIR)

        # DNS Resolver must have been restored
        if open('/etc/resolv.conf').read() != orig_resolv:
            raise error.TestFail('Nameserver settings not restored')

        # Routing table must have been restored
        cmd = ( 'ip', 'route', 'show' )
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        data, errdata = proc.communicate()
        if proc.returncode != 0:
            raise error.TestFail('Could not retrieve routing table')
        if data != orig_routing_table:
            raise error.TestFail('Routing table not restored')

    def cleanup(self):
        self._listener.stop()
