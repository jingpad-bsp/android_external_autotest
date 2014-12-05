# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib.cros.tendo import privetd_helper
from autotest_lib.server import test

class privetd_WebServerSanity(test.test):
    """Test that we can connect to privetd's web server and get a response
    from a simple GET request."""
    version = 1

    def warmup(self, host):
        self.helper = privetd_helper.PrivetdHelper(host=host)
        self.helper.restart_privetd(log_verbosity=3, enable_ping=True)


    def cleanup(self, host):
        self.helper.restart_privetd()


    def run_once(self, host):
        self.helper.ping_server()
        self.helper.ping_server(use_https=True)
