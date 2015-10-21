# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a server side USB playback audio test using the Chameleon board."""

import logging
import os
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.audio import audio_test_data
from autotest_lib.client.cros.chameleon import audio_test_utils
from autotest_lib.client.cros.chameleon import chameleon_audio_helper
from autotest_lib.client.cros.chameleon import chameleon_audio_ids
from autotest_lib.server.cros.audio import audio_test
from autotest_lib.server.cros.multimedia import remote_facade_factory


class audio_AudioBasicUSBRecord(audio_test.AudioTest):
    """Server side USB capture audio test.

    This test talks to a Chameleon board and a Cros device to verify
    USB audio record function of the Cros device.

    """
    version = 1
    RECORD_SECONDS = 5
    DELAY_AFTER_BINDING = 3

    def run_once(self, host):
        golden_file = audio_test_data.SWEEP_TEST_FILE

        chameleon_board = host.chameleon
        factory = remote_facade_factory.RemoteFacadeFactory(host)

        chameleon_board.reset()

        widget_factory = chameleon_audio_helper.AudioWidgetFactory(
                factory, host)

        source = widget_factory.create_widget(
            chameleon_audio_ids.ChameleonIds.USBOUT)
        recorder = widget_factory.create_widget(
            chameleon_audio_ids.CrosIds.USBIN)
        binder = widget_factory.create_binder(source, recorder)

        with chameleon_audio_helper.bind_widgets(binder):
            # Checks the node selected by cras is correct.
            time.sleep(self.DELAY_AFTER_BINDING)
            audio_facade = factory.create_audio_facade()

            audio_test_utils.dump_cros_audio_logs(
                    host, audio_facade, self.resultsdir, 'after_binding')

            output_nodes, _ = audio_facade.get_selected_node_types()
            if output_nodes != ['USB']:
                raise error.TestFail(
                        '%s rather than USB is selected on Cros '
                        'device' % output_nodes)

            logging.info('Setting playback data on Cros device')

            audio_facade.set_selected_output_volume(70)

            source.set_playback_data(golden_file)

            # Starts playing from Chameleon (which waits for Cros device),
            # waits for some time, and then starts recording from Cros device.
            logging.info('Start playing %s on Chameleon device',
                         golden_file.path)
            source.start_playback()

            logging.info('Start recording from Cros.')
            recorder.start_recording()

            time.sleep(self.RECORD_SECONDS)

            recorder.stop_recording()
            logging.info('Stopped recording from Cros.')

            audio_test_utils.dump_cros_audio_logs(
                    host, audio_facade, self.resultsdir, 'after_recording')

            recorder.read_recorded_binary()
            logging.info('Read recorded binary from Cros.')

        recorded_file = os.path.join(self.resultsdir, "recorded.raw")
        logging.info('Saving recorded data to %s', recorded_file)
        recorder.save_file(recorded_file)

        if not chameleon_audio_helper.compare_recorded_result(
                golden_file, recorder, 'correlation'):
            raise error.TestFail(
                    'Recorded file does not match playback file')
