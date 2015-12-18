# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This class defines the ADBHost Label class."""

import common

from autotest_lib.server.cros.dynamic_suite import constants
from autotest_lib.server.hosts import base_label
from autotest_lib.server.hosts import common_label


BOARD_FILE = 'ro.product.device'


class BoardLabel(base_label.StringPrefixLabel):
    """Determine the correct board label for the device."""

    _NAME = constants.BOARD_PREFIX.rstrip(':')

    # pylint: disable=missing-docstring
    def generate_labels(self, host):
        board = host.get_board_name()
        board_os = host.get_os_type()
        # Android boards could have a brillo OS so to differentiate between
        # the two, we're going to include the os with the board.
        return ['-'.join([board_os, board])]


ADB_LABELS = [
    BoardLabel(),
    common_label.OSLabel(),
]
