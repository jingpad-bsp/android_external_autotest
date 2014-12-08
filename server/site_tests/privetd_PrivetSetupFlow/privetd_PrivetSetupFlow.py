# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.tendo import privetd_helper
from autotest_lib.server import test

class privetd_PrivetSetupFlow(test.test):
    """This test validates the privet pairing/authentication/setup flow."""
    version = 1

    def warmup(self, host):
        self.helper = privetd_helper.PrivetdHelper(host=host)
        self.helper.restart_privetd(log_verbosity=3, enable_ping=True)
        self.helper.ping_server()  # Make sure the server is up and running.


    def cleanup(self, host):
        self.helper.restart_privetd()


    def run_once(self, host):
        # TODO(avakulenko): implement this
        pass
