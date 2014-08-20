# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a server side stressing DUT by switching Chameleon EDID."""

import glob
import logging
import os

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.chameleon import edid
from autotest_lib.server.cros.chameleon import chameleon_test


class display_EdidStress(chameleon_test.ChameleonTest):
    """Server side external display test.

    This test switches Chameleon EDID from among a large pool of EDIDs, tests
    DUT recognizes the emulated monitor and emits the correct video signal to
    Chameleon.
    """
    version = 1


    def initialize(self, host):
        super(display_EdidStress, self).initialize(host)
        self.backup_edid()


    def cleanup(self):
        super(display_EdidStress, self).cleanup()
        self.restore_edid()


    def run_once(self, host):
        errors = []
        edid_path = os.path.join(self.bindir, 'test_data', 'edids', '*')
        logging.info('See the display on Chameleon: port %d (%s)',
                     self.chameleon_port.get_connector_id(),
                     self.chameleon_port.get_connector_type())

        for filepath in glob.glob(edid_path):
            filename = os.path.basename(filepath)
            logging.info('Apply EDID: %s...', filename)
            self.chameleon_port.apply_edid(edid.Edid.from_file(filepath))

            try:
                logging.info('Reconnect output...')
                self.display_client.reconnect_output_and_wait()

                chameleon_resolution = self.chameleon_port.get_resolution()
                logging.info('See the resolution on Chameleon: %dx%d',
                             *chameleon_resolution)

                framebuffer_resolution = self.display_client.get_resolution()
                logging.info('See the resolution on framebuffer: %dx%d',
                             *framebuffer_resolution)
                if chameleon_resolution == framebuffer_resolution:
                    logging.info('Resolutions match.')
                else:
                    error_message = ('Resolutions not match on EDID %s: '
                                     '(chameleon) %dx%d != %dx%d (dut)' %
                                     ((filename, ) + chameleon_resolution +
                                      framebuffer_resolution))
                    logging.error(error_message)
                    errors.append(error_message)
            finally:
                self.display_client.close_tab()

        if errors:
            raise error.TestFail('; '.join(errors))
