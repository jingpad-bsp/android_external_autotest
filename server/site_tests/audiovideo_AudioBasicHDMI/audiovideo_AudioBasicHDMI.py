# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a server side HDMI audio test using the Chameleon board."""

import logging
import os
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.audio import audio_helper
from autotest_lib.client.cros.audio import audio_test_data
from autotest_lib.server.cros.chameleon import chameleon_test


class audiovideo_AudioBasicHDMI(chameleon_test.ChameleonTest):
    """Server side HDMI audio test.

    This test talks to a Chameleon board and a DUT to verify
    HDMI audio function of the DUT.
    """
    version = 1
    DELAY_BEFORE_PLAYBACK = 2
    DELAY_AFTER_PLAYBACK = 2


    def run_once(self, host):
        golden_file = audio_test_data.SWEEP_TEST_FILE
        channel_map = [1, 0, None, None, None, None, None, None]

        self.audio_start_recording('Chameleon', 'HDMI')
        time.sleep(self.DELAY_BEFORE_PLAYBACK)
        logging.info('Start playing %s on DUT', golden_file.path_on_dut)
        self.audio_playback('DUT', golden_file.path_on_dut)
        logging.info('Stopped playing %s on DUT', golden_file.path_on_dut)
        time.sleep(self.DELAY_AFTER_PLAYBACK)
        recorded_data_binary, recorded_data_format = self.audio_stop_recording(
                'Chameleon', 'HDMI')

        recorded_file = os.path.join(self.resultsdir, "recorded.raw")
        with open(recorded_file, 'wb') as f:
            logging.debug('Saving recorded raw file %s', recorded_file)
            f.write(recorded_data_binary)

        with open(golden_file.path_on_server, 'rb') as f:
            golden_data_binary = f.read()
            logging.info('Comparing recorded file %s with golden file %s ...',
                         recorded_file, golden_file.path_on_server)
            if not audio_helper.compare_data(
                    golden_data_binary, golden_file.data_format,
                    recorded_data_binary, recorded_data_format, channel_map,
                    'correlation'):
                raise error.TestError('Recorded file does not match playback file')
