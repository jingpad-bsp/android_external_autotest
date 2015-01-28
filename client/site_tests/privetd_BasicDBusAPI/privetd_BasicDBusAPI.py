# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.tendo import privetd_helper
from autotest_lib.client.cros.tendo import privetd_dbus_helper

class privetd_BasicDBusAPI(test.test):
    """Check that basic privetd daemon DBus APIs are functional."""
    version = 1


    def run_once(self):
        """Test entry point."""
        # Initially, disable bootstapping.
        config = privetd_helper.PrivetdConfig(
                wifi_bootstrap_mode=privetd_helper.BOOTSTRAP_CONFIG_DISABLED,
                gcd_bootstrap_mode=privetd_helper.BOOTSTRAP_CONFIG_DISABLED,
                log_verbosity=3)
        self.privetd = privetd_dbus_helper.make_dbus_helper(config)
        expected_response = 'Hello world!'
        actual_response = self.privetd.manager.Ping()
        if expected_response != actual_response:
            raise error.TestFail('Expected Manager.Ping to return %s '
                                 'but got %s instead.' % (expected_response,
                                                          actual_response))
        actual_state = self.privetd.wifi_bootstrap_status
        if actual_state != privetd_helper.WIFI_BOOTSTRAP_STATE_DISABLED:
            raise error.TestFail('Expected WiFi bootstrapping to be disabled, '
                                 'but it was %r' % actual_state)


    def clean(self):
        """Clean up processes altered during the test."""
        privetd_helper.PrivetdConfig.naive_restart()

