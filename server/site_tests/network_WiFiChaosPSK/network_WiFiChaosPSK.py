# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.server import autotest, test


class network_WiFiChaosPSK(test.test):
    """Tests connecting to APs using PSK security setting."""

    version = 1


    def run_once(self, host, helper, tries=1):
        """ Main entry function for autotest.

        @param host: an Autotest host object, DUT.
        @param helper: a WiFiChaosConnectionTest object, ready to use.
        @param tries: an integer, number of connection attempts.
        """
        helper.check_webdriver_available()
        # Override PSK password in base helper class
        helper.psk_password = 'chromeos'

        # Install all of the autotest libraries on the client
        client_at = autotest.Autotest(host)
        client_at.install()

        helper.set_outputdir(self.outputdir)

        all_aps = helper.factory.get_aps_with_security_mode(
                      helper.generic_ap.security_type_wpapsk)
        helper.power_down(all_aps)

        helper.loop_ap_configs_and_test(all_aps, tries, helper.PSK)
        logging.info('Client test complete, powering down routers.')
        helper.power_down(all_aps)

        helper.check_test_error()
