# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a server side internal speaker test using the Chameleon board."""

import logging
import os
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.audio import audio_test_data
from autotest_lib.client.cros.chameleon import chameleon_audio_helper
from autotest_lib.client.cros.chameleon import chameleon_audio_ids
from autotest_lib.server import test
from autotest_lib.server.cros.multimedia import remote_facade_factory


class audio_AudioBasicInternalSpeaker(test.test):
    """Server side internal speaker audio test.

    This test talks to a Chameleon board and a Cros device to verify
    internal speaker audio function of the Cros device.

    """
    version = 1
    DELAY_BEFORE_RECORD_SECONDS = 0.5
    RECORD_SECONDS = 8

    def run_once(self, host):
        golden_file = audio_test_data.SIMPLE_FREQUENCY_TEST_FILE

        chameleon_board = host.chameleon
        factory = remote_facade_factory.RemoteFacadeFactory(host)

        chameleon_board.reset()

        widget_factory = chameleon_audio_helper.AudioWidgetFactory(
                chameleon_board, factory)

        source = widget_factory.create_widget(
            chameleon_audio_ids.CrosIds.SPEAKER)

        recorder = widget_factory.create_widget(
            chameleon_audio_ids.ChameleonIds.MIC)

        audio_facade = factory.create_audio_facade()

        # Checks the node selected by cras is correct.
        output_node, _ = audio_facade.get_selected_node_types()
        if output_node != 'INTERNAL_SPEAKER':
            raise error.TestError(
                    '%s rather than internal speaker is selected on Cros '
                    'device' % output_node)

        audio_facade.set_selected_output_volume(80)

        # Starts playing, waits for some time, and then starts recording.
        # This is to avoid artifact caused by codec initialization.
        logging.info('Start playing %s on Cros device',
                     golden_file.path)
        source.start_playback(golden_file)

        time.sleep(self.DELAY_BEFORE_RECORD_SECONDS)
        logging.info('Start recording from Chameleon.')
        recorder.start_recording()

        time.sleep(self.RECORD_SECONDS)

        recorder.stop_recording()
        logging.info('Stopped recording from Chameleon.')

        recorded_file = os.path.join(self.resultsdir, "recorded.raw")
        logging.info('Saving recorded data to %s', recorded_file)
        recorder.save_file(recorded_file)

        # Removes the beginning of recorded data. This is to avoid artifact
        # caused by Chameleon codec initialization in the beginning of
        # recording.
        recorder.remove_head(0.5)

        # Removes noise by a lowpass filter.
        recorder.lowpass_filter(1000)
        recorded_file = os.path.join(self.resultsdir, "recorded_filtered.raw")
        logging.info('Saving filtered data to %s', recorded_file)
        recorder.save_file(recorded_file)

        # Compares data by frequency. Audio signal recorded by microphone has
        # gone through analog processing and through the air.
        # This suffers from codec artifacts and noise on the path.
        # Comparing data by frequency is more robust than comparing by
        # correlation, which is suitable for fully-digital audio path like USB
        # and HDMI.
        if not chameleon_audio_helper.compare_recorded_result(
                golden_file, recorder, 'frequency'):
            raise error.TestError(
                    'Recorded file does not match playback file')
