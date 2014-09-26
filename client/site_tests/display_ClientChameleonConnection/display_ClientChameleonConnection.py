# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a client-side test to check the Chameleon connection."""

import logging

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.chameleon import chameleon
from autotest_lib.client.cros.chameleon import chameleon_port_finder


class display_ClientChameleonConnection(test.test):
    """Chameleon connection client test.

    This test talks to a Chameleon board from DUT. Try to plug the Chameleon
    ports and see if DUT detects them.
    """
    version = 1

    _TIMEOUT_VIDEO_STABLE_PROBE = 10


    def run_once(self, host, args):
        self.chameleon = chameleon.create_chameleon_board(host.hostname, args)
        self.chameleon.reset()

        finder = chameleon_port_finder.ChameleonPortFinder(self.chameleon)
        ports = finder.find_all_ports()

        connected_ports = ports.connected
        dut_failed_ports = ports.failed

        msg = str(finder)
        logging.debug(msg)

        if dut_failed_ports or not connected_ports:
            raise error.TestFail(msg)
