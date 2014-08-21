# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a client-side test to check the Chameleon connection."""

import logging

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.chameleon import chameleon


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

        connected_ports = []
        dut_failed_ports = []
        for chameleon_port in self.chameleon.get_all_ports():
            connector_type = chameleon_port.get_connector_type()
            # Try to plug the port such that DUT can detect it.
            chameleon_port.plug()
            # DUT takes some time to respond. Wait until the video signal
            # to stabilize.
            chameleon_port.wait_video_input_stable(
                    self._TIMEOUT_VIDEO_STABLE_PROBE)

            # Add the connected ports if they are detected by xrandr.
            xrandr_output = utils.get_xrandr_output_state()
            for output in xrandr_output.iterkeys():
                if output.startswith(connector_type):
                    connected_ports.append(chameleon_port)
                    break
            else:
                dut_failed_ports.append(chameleon_port)

            # Unplug the port afterward.
            chameleon_port.unplug()

        if connected_ports:
            ports_to_str = lambda ports: ', '.join(
                    '%s(%d)' % (p.get_connector_type(), p.get_connector_id())
                    for p in ports)
            logging.info('Detected %d connected ports: %s',
                         len(connected_ports), ports_to_str(connected_ports))
            if dut_failed_ports:
                message = 'DUT failed to detect Chameleon ports: %s' % (
                        ports_to_str(dut_failed_ports))
                logging.error(message)
                raise error.TestFail(message)
        else:
            raise error.TestFail('No port connected to Chameleon')
