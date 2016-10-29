# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Server side bluetooth tests on adapter advertising."""

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.bluetooth import bluetooth_adpater_tests
from autotest_lib.server.cros.multimedia import bluetooth_le_facade_adapter


class bluetooth_AdapterLEAdvertising(
        bluetooth_adpater_tests.BluetoothAdapterTests):
    """Server side bluetooth adapter advertising Test.

    This class tries to test the adapter could advertise with correct
    parameters.

    In particular, the following subtests are performed. Look at the
    docstrings of the subtests for more details.
    - test_register_advertisement
    - test_set_advertising_intervals
    - test_reset_advertising

    Refer to BluetoothAdapterTests for the implementation of the subtests
    performed in this autotest test.

    If the advertisement data in a control file is registered multiple
    times, the advertising data issued by HCI commands may be omitted
    by kernel and results in test failure. In this case, reboot the DUT
    to avoid the test failure.

    """
    def test_registration_and_reset(self, advertisements, min_adv_interval_ms,
                                    max_adv_interval_ms):
        """Test advertisements operations with new intervals.

        @param advertisements: a list of advertisement instances.
        @param min_adv_interval_ms: min_adv_interval in milli-second.
        @param max_adv_interval_ms: max_adv_interval in milli-second.

        """
        # Create a list of advertisement instance IDs starting at 1.
        instance_ids = range(1, len(advertisements) + 1)

        # Test if the specified advertisements could be registered correctly.
        for instance_id, advertisement in zip(instance_ids, advertisements):
            self.test_register_advertisement(advertisement,
                                             instance_id,
                                             min_adv_interval_ms,
                                             max_adv_interval_ms)

        # Test if advertising is reset correctly.
        self.test_reset_advertising(instance_ids)


    def run_once(self, host, advertisements, multi_advertising,
                 min_adv_interval_ms, max_adv_interval_ms):
        """Running Bluetooth adapter LE advertising autotest.

        @param host: device under test host.
        @param advertisements: a list of advertisement instances.
        @param multi_advertising: indicating if this is multi-advertising.
        @param min_adv_interval_ms: min_adv_interval in milli-second.
        @param max_adv_interval_ms: max_adv_interval in milli-second.

        """
        self.host = host
        self.advertisements = advertisements
        ble_adapter = bluetooth_le_facade_adapter.BluetoothLEFacadeRemoteAdapter
        self.bluetooth_le_facade = ble_adapter(self.host)
        self.bluetooth_facade = self.bluetooth_le_facade

        # Reset the adapter to forget previous stored data and turn it on.
        self.test_reset_on_adapter()

        # Test if new advertising intervals could be set correctly.
        self.test_set_advertising_intervals(min_adv_interval_ms,
                                            max_adv_interval_ms)

        if multi_advertising:
            # For multiple advertisements, test all instances with the specified
            # advertising intervals.
            self.test_registration_and_reset(
                    advertisements,
                    min_adv_interval_ms,
                    max_adv_interval_ms)

            # Test all instances with default advertising intervals.
            self.test_registration_and_reset(
                    advertisements,
                    self.DAFAULT_MIN_ADVERTISEMENT_INTERVAL_MS,
                    self.DAFAULT_MAX_ADVERTISEMENT_INTERVAL_MS)

        else:
            # For single advertisement, test the 1st advertisement with the
            # specified advertising intervals.
            self.test_registration_and_reset(
                    advertisements[0:1],
                    min_adv_interval_ms,
                    max_adv_interval_ms)

            # Test the 2nd advertisement with default advertising intervals.
            # Note: it is required to change the advertisement instance
            #       so that the advertisement data could be monitored by btmon.
            #       Otherwise, the advertisement data would be just cached and
            #       reused such that the data would not be visible in btmon.
            self.test_registration_and_reset(
                    advertisements[1:2],
                    self.DAFAULT_MIN_ADVERTISEMENT_INTERVAL_MS,
                    self.DAFAULT_MAX_ADVERTISEMENT_INTERVAL_MS)

        if self.fails:
            raise error.TestFail(self.fails)
