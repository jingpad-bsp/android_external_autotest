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

    # Boards which do not have Bluetooth or do not ship.
    _INVALID_BOARDS = ['x86-alex', 'x86-alex_he', 'lumpy', 'rambi']

    def warmup(self):
        """Overwrite parent warmup; no need to log in."""
        pass

    def _check_id(self):
      """Fail if the Bluetooth ID is not in the correct format."""
      adapter_info = self._get_adapter_info()
      modalias = adapter_info['Modalias']
      logging.info('Saw Bluetooth ID of: %s', modalias)

      if not re.match('bluetooth:v00E0p24..d0400', modalias):
          raise error.TestError('%s does not match expected format!' % modalias)


    def run_once(self):
        """Entry point of this test."""

        # Abort test for invalid boards.
        device = utils.get_board()
        if device in self._INVALID_BOARDS:
            logging.info('Aborting test; %s does not have Bluetooth.', device)
            return

        self._check_id()


