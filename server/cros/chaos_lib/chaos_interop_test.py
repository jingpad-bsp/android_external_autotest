# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server import packet_capture
from autotest_lib.server.cros.chaos_ap_configurators import ap_batch_locker
from autotest_lib.server.cros.chaos_lib import chaos_base_test


def wifi_chaos_open(host, ap_spec, batch_size, tries):
    """Runs Chaos test on open system DUT.

    @param host: an Autotest host object, device under test.
    @param ap_spec: a Python dictionary, desired attributes of Chaos APs.
    @param batch_size: an integer, max. number of APs to lock in one batch.
    @param tries: an integer, number of iterations to run per AP.

    """
    with packet_capture.PacketCaptureManager() as capturer:
        capturer.allocate_packet_capture_machine()
        helper = chaos_base_test.WiFiChaosConnectionTest(host, capturer)
        with ap_batch_locker.ApBatchLockerManager(
                ap_spec=ap_spec) as batch_locker:
            while batch_locker.has_more_aps():
                ap_batch = batch_locker.get_ap_batch(batch_size=batch_size)
                if not ap_batch:
                    logging.info('No more APs to test.')
                    break

                # Power down all of the APs because some can get grumpy
                # if they are configured several times and remain on.
                helper.power_down_aps(ap_batch)

                # For dual-band AP, we can only configure and test one band
                # at a time. Hence the use of nested for loops below.
                for band, channel in helper.get_bands_and_channels():
                    for ap_info in helper.config_aps(ap_batch, band, channel):
                        # Group test output by SSID
                        mod_ssid = ap_info['ssid'].replace(' ', '_')
                        job.run_test('network_WiFiChaosOpen',
                                     host=host,
                                     helper=helper,
                                     ap_info=ap_info,
                                     tries=tries,
                                     disable_sysinfo=False,
                                     tag=mod_ssid)

                batch_locker.unlock_aps()
