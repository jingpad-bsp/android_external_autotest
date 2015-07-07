# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a server side bluetooth record test using the Chameleon board."""

import logging
import os
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.audio import audio_test_data
from autotest_lib.client.cros.chameleon import chameleon_audio_helper
from autotest_lib.client.cros.chameleon import chameleon_audio_ids
from autotest_lib.server.cros.audio import audio_test
from autotest_lib.server.cros.multimedia import remote_facade_factory


class audio_AudioBasicBluetoothRecord(audio_test.AudioTest):
    """Server side bluetooth record audio test.

    This test talks to a Chameleon board and a Cros device to verify
    bluetooth record audio function of the Cros device.

    """
    version = 1
    DELAY_BEFORE_RECORD_SECONDS = 0.5
    RECORD_SECONDS = 5

    def run_once(self, host):
        golden_file = audio_test_data.SIMPLE_FREQUENCY_TEST_FILE

        factory = remote_facade_factory.RemoteFacadeFactory(host)
        audio_facade = factory.create_audio_facade()

        chameleon_board = host.chameleon
        chameleon_board.reset()

        widget_factory = chameleon_audio_helper.AudioWidgetFactory(
                factory, host)

        source = widget_factory.create_widget(
            chameleon_audio_ids.ChameleonIds.LINEOUT)
        bluetooth_widget = widget_factory.create_widget(
            chameleon_audio_ids.PeripheralIds.BLUETOOTH_DATA_TX)
        recorder = widget_factory.create_widget(
            chameleon_audio_ids.CrosIds.BLUETOOTH_MIC)

        binder = widget_factory.create_binder(
                source, bluetooth_widget, recorder)

        with chameleon_audio_helper.bind_widgets(binder):

            # Checks the input node selected by Cras is internal microphone.
            # Checks crbug.com/495537 for the reason to lower bluetooth
            # microphone priority.
            _, input_nodes = audio_facade.get_selected_node_types()
            if input_nodes != ['INTERNAL_MIC']:
                raise error.TestError(
                        '%s rather than internal mic is selected on Cros '
                        'device' % input_nodes)

            # Selects bluetooth mic to be the active input node.
            audio_facade.set_selected_node_types([], ['BLUETOOTH'])

            # Checks the input node selected by Cras is bluetooth microphone.
            _, input_nodes = audio_facade.get_selected_node_types()
            if input_nodes != ['BLUETOOTH']:
                raise error.TestError(
                        '%s rather than bluetooth is selected on Cros '
                        'device' % input_nodes)

            # Starts playing, waits for some time, and then starts recording.
            # This is to avoid artifact caused by codec initialization.
            source.set_playback_data(golden_file)
            logging.info('Start playing %s on Chameleon',
                         golden_file.path)
            source.start_playback()

            time.sleep(self.DELAY_BEFORE_RECORD_SECONDS)
            logging.info('Start recording from Cros device.')
            recorder.start_recording()

            time.sleep(self.RECORD_SECONDS)

            recorder.stop_recording()
            logging.info('Stopped recording from Cros device.')

            recorder.read_recorded_binary()
            logging.info('Read recorded binary from Chameleon.')

        recorded_file = os.path.join(self.resultsdir, "recorded.raw")
        logging.info('Saving recorded data to %s', recorded_file)
        recorder.save_file(recorded_file)

        # Removes noise by a lowpass filter.
        recorder.lowpass_filter(2000)
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
