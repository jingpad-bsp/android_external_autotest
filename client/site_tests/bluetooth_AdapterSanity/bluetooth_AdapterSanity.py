# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.bin import utils
from autotest_lib.client.cros.bluetooth import bluetooth_semiauto_helper


class bluetooth_AdapterSanity(
        bluetooth_semiauto_helper.BluetoothSemiAutoHelper):
    """Checks whether the Bluetooth adapter is present and working."""
    version = 1

    # Boards which do not have Bluetooth.
    _INVALID_BOARDS = ['x86-alex', 'x86-alex_he', 'lumpy']

    def warmup(self):
        """Overwrite parent warmup; no need to log in."""
        pass

    def run_once(self):
        """Entry point of this test."""

        # Abort test if this device does not support Bluetooth.
        device = utils.get_board()
        if device in self._INVALID_BOARDS:
            logging.info('Aborting test; %s does not have Bluetooth.', device)
            return

        # Start hcidump (other logs collected at failure).
        self.start_dump()

        # Enable then disable adapter
        self.set_adapter(adapter_status=True)
        self.wait_for_adapter(adapter_status=True)
        self.set_adapter(adapter_status=False)
        self.wait_for_adapter(adapter_status=False)

