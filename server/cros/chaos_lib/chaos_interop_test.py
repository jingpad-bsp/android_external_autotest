# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from datetime import datetime

from autotest_lib.server import packet_capture
from autotest_lib.server.cros.chaos_ap_configurators import ap_batch_locker
from autotest_lib.server.cros.chaos_lib import chaos_base_test


class WifiChaosTest(object):
    """Helper object to set up and run Chaos test.

    @attribute test: a string, test name.
    @attribute host: an Autotest host object, device under test.
    @attribute ap_spec: a Python dictionary, desired attributes of Chaos APs.
    @attribute PSK_TEST: a string, name of Chaos PSK test.
    """
    PSK_TEST = 'network_WiFiChaosPSK'


    def __init__(self, test, host):
        """Initializes and runs test.

        @param test: a string, test name.
        @param host: an Autotest host object, device under test.
        """
        self._test = test
        self._host = host
        self._ap_spec = None
        # Log server and DUT times
        dt = datetime.now()
        logging.info('Server time: %s', dt.strftime('%a %b %d %H:%M:%S %Y'))
        logging.info('DUT time: %s', self._host.run('date').stdout.strip())


    def _setup(self, capturer):
        """Performs necessary setup before running Chaos test.

        @param capturer: a PacketCaptureManager object.
        @returns a WiFiChaosConnectionTest object.
        """
        helper = chaos_base_test.WiFiChaosConnectionTest(self._host, capturer)
        if self._test == self.PSK_TEST:
            logging.info('Perform additional setup for PSK test.')
            helper.psk_password = 'chromeos'
            psk_spec = {'securities': [helper.ap_config.SECURITY_TYPE_WPAPSK]}
            # Update ap_spec w/ PSK security
            self._ap_spec = dict(self._ap_spec.items() + psk_spec.items())

        return helper


    def run(self, job, ap_spec, batch_size, tries):
        """Executes Chaos test.

        @param job: an Autotest job object.
        @param ap_spec: a Python dictionary, desired attributes of Chaos APs.
        @param batch_size: an integer, max number of APs to lock in one batch.
        @param tries: an integer, number of iterations to run per AP.
        """
        self._ap_spec = ap_spec
        with packet_capture.PacketCaptureManager() as capturer:
            capturer.allocate_packet_capture_machine()
            helper = self._setup(capturer)
            with ap_batch_locker.ApBatchLockerManager(
                    ap_spec=self._ap_spec) as batch_locker:
                while batch_locker.has_more_aps():
                    ap_batch = batch_locker.get_ap_batch(
                            batch_size=batch_size)
                    if not ap_batch:
                        logging.info('No more APs to test.')
                        break

                    # Power down all of the APs because some can get grumpy
                    # if they are configured several times and remain on.
                    helper.power_down_aps(ap_batch)
                    security = ''
                    if helper.psk_password != '':
                        security = helper.PSK

                    # Test 2.4GHz band first, followed by 5GHz band. Release
                    # APs as soon as we're done using them.
                    aps_unlocked = set()
                    for band in [helper.ap_config.BAND_2GHZ,
                                 helper.ap_config.BAND_5GHZ]:

                        # Remove 2.4GHz-only APs before APs for 5GHz run
                        if band == helper.ap_config.BAND_5GHZ:
                            ap_batch = list(set(ap_batch) - aps_unlocked)

                        for ap_info in helper.config_aps(
                                ap_batch, band, security=security):
                            # Group test output by SSID
                            mod_ssid = ap_info['ssid'].replace(' ', '_')
                            job.run_test(self._test,
                                         host=self._host,
                                         helper=helper,
                                         ap_info=ap_info,
                                         tries=tries,
                                         disable_sysinfo=False,
                                         tag=mod_ssid)
                            if ap_info['ok_to_unlock']:
                                batch_locker.unlock_one_ap(
                                        ap_info['configurator'].host_name)
                                aps_unlocked.add(ap_info['configurator'])

                    batch_locker.unlock_aps()
