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
    def run_once(self, host, advertisement_data, min_adv_interval_ms,
                 max_adv_interval_ms):
        """Running Bluetooth adapter LE advertising autotest.

        @param host: device under test host
        @param advertisement_data: the advertisement data
        @param min_adv_interval_ms: min_adv_interval in milli-second.
        @param max_adv_interval_ms: max_adv_interval in milli-second.

        """
        self.host = host
        ble_adapter = bluetooth_le_facade_adapter.BluetoothLEFacadeRemoteAdapter
        self.bluetooth_le_facade = ble_adapter(self.host)

        # Test if an advertisement could be registered correctly.
        self.test_register_advertisement(advertisement_data)

        # Test if new advertising intervals could be set correctly.
        self.test_set_advertising_intervals(min_adv_interval_ms,
                                            max_adv_interval_ms)

        # Test if advertising is reset correctly.
        self.test_reset_advertising()

        if self.fails:
            raise error.TestFail(self.fails)
