# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.tendo import privetd_helper

class privetd_BasicDBusAPI(test.test):
    """Check that basic privetd daemon DBus APIs are functional."""
    version = 1

    def initialize(self):
        """Set up the objects we're going to use in the test."""
        # We define all the objects we're going to clean up as None, because
        # an exception part of the way through initializing will cause some
        # of those objects to be undefined names.  This causes cleanup to
        # fail with odd messages about "object self has no such field XXX".
        self.privetd = None
        self.privetd = privetd_helper.make_helper(
                wifi_bootstrap_mode=privetd_helper.BOOTSTRAP_CONFIG_DISABLED,
                gcd_bootstrap_mode=privetd_helper.BOOTSTRAP_CONFIG_DISABLED,
                verbosity_level=3)

    def run_once(self):
        """Test entry point."""
        expected_response = 'Hello world!'
        actual_response = self.privetd.manager.Ping()
        if expected_response != actual_response:
            raise error.TestFail('Expected Manager.Ping to return %s '
                                 'but got %s instead.' % (expected_response,
                                                          actual_response))

        # Initially, bootstrapping should be disabled entirely.
        actual_state = self.privetd.wifi_bootstrap_status
        if actual_state != privetd_helper.WIFI_BOOTSTRAP_STATE_DISABLED:
            raise error.TestFail('Expected WiFi bootstrapping to be disabled, '
                                 'but it was %r' % actual_state)


    def clean(self):
        """Clean up processes altered during the test."""
        if self.privetd is not None:
            self.privetd.close()

