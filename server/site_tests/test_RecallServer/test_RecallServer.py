# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cPickle as pickle
import logging
import os

from autotest_lib.client.common_lib import error
from autotest_lib.server import test, autotest
from autotest_lib.server.cros import recall_test, recall

class test_RecallServer(recall_test.RecallServerTest):
    version = 1

    _certificate_authority_subject = "/O=Google/OU=Chromium OS Test Server"

    def initialize(self, host, pickle_file=None, proxy_only=False):
        if pickle_file is not None:
            logging.info("Restoring from pickle %s", pickle_file)
            self.certificate_authority, self.dns_client, self.http_client \
                = pickle.load(open(pickle_file))
        else:
            logging.info("Setting up recall server")
            self.certificate_authority = recall.CertificateAuthority(
                subject=self._certificate_authority_subject,
                default_days=1)

            if proxy_only:
                self.dns_client = recall.DNSClient()
                self.http_client = recall.HTTPClient()
            else:
                self.dns_client = recall.SymmetricDNSClient()
                self.http_client = recall.ArchivingHTTPClient(
                    recall.DeterministicScriptInjector())

        recall_test.RecallServerTest.initialize(self, host)

    def run_once(self, host, test, proxy_only=False, num_iterations=1, **args):
        logging.info("Running test %s on remote client %s", test, host.ip)
        self.RunTestOnHost(test, host, **args)

        # Remove the second-level client so further iterations, including
        # later runs with the pickle we write out, don't proxy
        del self.dns_client.dns_client
        del self.http_client.http_client
        logging.info("Recording/proxying disabled")

        if not proxy_only:
            dump_file = os.path.join(self.resultsdir, 'pickle')
            logging.debug("Saving results to %s", dump_file)
            pickle.dump((self.certificate_authority,
                         self.dns_client, self.http_client),
                        open(dump_file, 'w'))

        # Repeat test for subsequent iterations now proxying is disabled
        if isinstance(num_iterations, str):
            num_iterations = int(num_iterations)
        if num_iterations > 1:
            logging.info("Running %d more iterations", num_iterations - 1)
            self.RunTestOnHost(test, host, iterations=(num_iterations - 1),
                               **args)
