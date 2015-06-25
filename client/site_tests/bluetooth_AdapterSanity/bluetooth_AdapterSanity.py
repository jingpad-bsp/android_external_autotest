# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.cros.bluetooth import bluetooth_semiauto_helper


class bluetooth_AdapterSanity(
        bluetooth_semiauto_helper.BluetoothSemiAutoHelper):
    """Checks whether the Bluetooth adapter is present and working."""
    version = 1

    def warmup(self):
        """Overwrite parent warmup; no need to log in."""
        pass

    def run_once(self):
        """Entry point of this test."""
        if not self.supports_bluetooth():
            return

        # Start btmon running (other logs collected at failure).
        self.start_dump()

        self.poll_adapter_presence()

        # Enable then disable adapter.
        self.set_adapter_power(True)
        self.set_adapter_power(False)
