# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import pprint

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server import test


class network_WiFi_ChaosConnectDisconnect(test.test):
    """ Dynamic Chaos test to connect and disconnect to an AP. """

    version = 1


    def run_once(self, capturer, host, ap_spec, client, tries):
        """ Main entry function for autotest.

        @param capturer: a packet capture device
        @param host: an Autotest host object, DUT.
        @param ap_spec: an APSpec object
        @param client: WiFiClient object
        @param tries: an integer, number of connection attempts.

        """

        assoc_params = ap_spec.association_parameters
        results = []

        for i in range(1, tries + 1):
            client.shill.disconnect(assoc_params.ssid)
            if not client.shill.init_test_network_state():
                return 'Failed to set up isolated test context profile.'

            # TODO(wiley) We probably don't always want HT40, but
            #             this information is hard to infer here.
            #             Change how AP configuration happens so that
            #             we expose this.
            capturer.start_capture(ap_spec.frequency, ht_type='HT40+')
            try:
                success = False
                logging.info('Connection attempt %d', i)
                assoc_result = xmlrpc_datatypes.deserialize(
                        client.shill.connect_wifi(assoc_params))
                success = assoc_result.success
                if not success:
                    logging.info('Connection attempt %d failed; reason: %s',
                                 i, assoc_result.failure_reason)
                    results.append(
                            {'try' : i,
                             'error' : assoc_result.failure_reason})
                else:
                    logging.info('Connection attempt %d passed', i)
            finally:
                filename = str('connect_try_%d_%s.trc' % (i,
                               ('success' if success else 'fail')))
                capturer.stop_capture(save_dir=self.outputdir,
                                      save_filename=filename)
                client.shill.disconnect(assoc_params.ssid)
                client.shill.clean_profiles()

        if len(results) > 0:
            # error.TestError doesn't handle the formatting inline, doing it
            # here so it is clearer to read in the status.log file.
            msg = str('Failed on the following attempts:\n%s\n'
                      'With the ap_spec:\n%s' % (pprint.pformat(results),
                      ap_spec))
            raise error.TestFail(msg)
