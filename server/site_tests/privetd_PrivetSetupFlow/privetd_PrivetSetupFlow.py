# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib.cros.tendo import privetd_helper
from autotest_lib.server import test

class privetd_PrivetSetupFlow(test.test):
    """This test validates the privet pairing/authentication/setup flow."""
    version = 1

    def warmup(self, host):
        config =privetd_helper.PrivetdConfig(log_verbosity=3, enable_ping=True)
        config.restart_with_config(host=host)


    def cleanup(self, host):
        privetd_helper.PrivetdConfig.naive_restart(host=host)


    def run_once(self, host):
        helper = privetd_helper.PrivetdHelper(host=host)
        helper.ping_server()  # Make sure the server is up and running.
        # TODO(avakulenko): implement this
