# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.server import autotest, test


class network_WiFiSimpleConnectionServer(test.test):
    """ Dynamic Chaos test. """

    version = 1


    def run_once(self, host, helper, tries=1):
        """ Main entry function for autotest.

        @param host: an Autotest host object, DUT.
        @param helper: a WiFiChaosConnectionTest object, ready to use.
        @param tries: an integer, number of connection attempts.
        """
        helper.check_webdriver_available()

        # Install all of the autotest libriaries on the client
        client_at = autotest.Autotest(host)
        client_at.install()

        helper.set_outputdir(self.outputdir)
        all_aps = helper.factory.get_ap_configurators()
        helper.power_down(all_aps)

        helper.loop_ap_configs_and_test(all_aps, tries)
        logging.info('Client test complete, powering down routers.')
        helper.power_down(all_aps)

        helper.check_test_error()
