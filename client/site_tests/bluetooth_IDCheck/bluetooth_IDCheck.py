# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.bluetooth import bluetooth_semiauto_helper


class bluetooth_IDCheck(bluetooth_semiauto_helper.BluetoothSemiAutoHelper):
    """Checks whether the Bluetooth ID is in the correct format."""
    version = 1

    # Boards which only support bluetooth version 3 and below
    _BLUETOOTH_3_BOARDS = ['x86-mario', 'x86-zgb']

    def warmup(self):
        """Overwrite parent warmup; no need to log in."""
        pass

    def _check_id(self):
        """Fail if the Bluetooth ID is not in the correct format."""
        device = utils.get_board()
        adapter_info = self._get_adapter_info()
        modalias = adapter_info['Modalias']
        logging.info('Saw Bluetooth ID of: %s', modalias)

        if device in self._BLUETOOTH_3_BOARDS:
            bt_format = 'bluetooth:v00E0p24..d0300'
        else:
            bt_format = 'bluetooth:v00E0p24..d0400'

        if not re.match(bt_format, modalias):
            raise error.TestError('%s does not match expected format: %s '
                                 % (modalias, bt_format))

    def run_once(self):
        """Entry point of this test."""
        if not self.supports_bluetooth():
            return

        self.poll_adapter_presence()
        self._check_id()
