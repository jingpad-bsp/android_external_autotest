# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


from autotest_lib.client.common_lib import error
from autotest_lib.server import test
from autotest_lib.server.cros.clique_lib import clique_dut_control


class network_WiFi_CliqueConnectDisconnect(test.test):
    """ Dynamic Clique test to connect and disconnect to an AP. """

    version = 1


    def run_once(self, capturer, capturer_frequency, capturer_ht_type,
                 dut_pool, assoc_params, tries, debug_info=None):
        """ Main entry function for autotest.

        @param capturer: a packet capture device
        @param capturer_frequency: integer channel frequency in MHz.
        @param capturer_ht_type: string specifier of channel HT type.
        @param dut_pool: the DUT pool to be used for the test. It is a 2D list
                         of DUTObjects.
        @param assoc_params: an AssociationParameters object.
        @param tries: an integer, number of connection attempts.
        @param debug_info: a string of additional info to display on failure

        """
        # We only need 1 set in the pool for this test.
        if len(dut_pool) != 1:
            raise error.TestFail("Incorrect pool configuration for this test.")

        dut_role_classes = [clique_dut_control.DUTRoleConnectDisconnect]
        test_params = { 'assoc_params': assoc_params,
                        'capturer': capturer,
                        'capturer_frequency': capturer_frequency,
                        'capturer_ht_type': capturer_ht_type,
                        'debug_info': debug_info }
        error_results = clique_dut_control.execute_dut_pool(
            dut_pool, dut_role_classes, test_params)
        if error_results:
            raise error.TestFail("Failed test. Error Results: %s" %
                                 str(error_results))
