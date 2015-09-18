# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This is a server side bluetooth playback/record test using the Chameleon
board.
"""

import logging
import os
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.audio import audio_test_data
from autotest_lib.client.cros.chameleon import chameleon_audio_helper
from autotest_lib.client.cros.chameleon import chameleon_audio_ids
from autotest_lib.server.cros.audio import audio_test
from autotest_lib.server.cros.multimedia import remote_facade_factory


class audio_AudioBasicBluetoothPlaybackRecord(audio_test.AudioTest):
    """Server side bluetooth playback/record audio test.

    This test talks to a Chameleon board and a Cros device to verify
    bluetooth playback/record audio function of the Cros device.

    """
    version = 1
    DELAY_BEFORE_RECORD_SECONDS = 0.5
    RECORD_SECONDS = 5

    def run_once(self, host):
        # Bluetooth HSP/HFP profile only supports one channel
        # playback/recording. So we should use simple frequency
        # test file which contains identical sine waves in two
        # channels.
        golden_file = audio_test_data.SIMPLE_FREQUENCY_TEST_FILE

        factory = remote_facade_factory.RemoteFacadeFactory(host)
        audio_facade = factory.create_audio_facade()

        chameleon_board = host.chameleon
        chameleon_board.reset()

        widget_factory = chameleon_audio_helper.AudioWidgetFactory(
                factory, host)

        playback_source = widget_factory.create_widget(
            chameleon_audio_ids.CrosIds.BLUETOOTH_HEADPHONE)
        playback_bluetooth_widget = widget_factory.create_widget(
            chameleon_audio_ids.PeripheralIds.BLUETOOTH_DATA_RX)
        playback_recorder = widget_factory.create_widget(
            chameleon_audio_ids.ChameleonIds.LINEIN)
        playback_binder = widget_factory.create_binder(
                playback_source, playback_bluetooth_widget, playback_recorder)

        record_source = widget_factory.create_widget(
            chameleon_audio_ids.ChameleonIds.LINEOUT)
        record_bluetooth_widget = widget_factory.create_widget(
            chameleon_audio_ids.PeripheralIds.BLUETOOTH_DATA_TX)
        record_recorder = widget_factory.create_widget(
            chameleon_audio_ids.CrosIds.BLUETOOTH_MIC)
        record_binder = widget_factory.create_binder(
                record_source, record_bluetooth_widget, record_recorder)

        with chameleon_audio_helper.bind_widgets(playback_binder):
            with chameleon_audio_helper.bind_widgets(record_binder):

                # Checks the input node selected by Cras is internal microphone.
                # Checks crbug.com/495537 for the reason to lower bluetooth
                # microphone priority.
                _, input_nodes = audio_facade.get_selected_node_types()
                if input_nodes != ['INTERNAL_MIC']:
                    raise error.TestFail(
                            '%s rather than internal mic is selected on Cros '
                            'device' % input_nodes)

                # Selects bluetooth mic to be the active input node.
                audio_facade.set_selected_node_types([], ['BLUETOOTH'])

                # Checks the node selected by Cras is correct.
                o_nodes, i_nodes = audio_facade.get_selected_node_types()
                if o_nodes != ['BLUETOOTH'] or i_nodes != ['BLUETOOTH']:
                    raise error.TestFail(
                            '(%s, %s) rather than (bluetooth, bluetooth) are '
                            'selected on Cros device' % (o_nodes, i_nodes))

                audio_facade.set_selected_output_volume(80)

                # Setup the playback data. This step is time consuming.
                playback_source.set_playback_data(golden_file)
                logging.info('Start playing %s on Cros device',
                             golden_file.path)
                record_source.set_playback_data(golden_file)
                logging.info('Start playing %s on Chameleon device',
                             golden_file.path)

                # Starts playing, waits for some time, and then starts recording.
                # This is to avoid artifact caused by codec initialization.
                playback_source.start_playback()
                record_source.start_playback()

                time.sleep(self.DELAY_BEFORE_RECORD_SECONDS)
                logging.info('Start recording from Chameleon.')
                playback_recorder.start_recording()
                logging.info('Start recording from Cros device.')
                record_recorder.start_recording()

                time.sleep(self.RECORD_SECONDS)

                playback_recorder.stop_recording()
                logging.info('Stopped recording from Chameleon.')
                record_recorder.stop_recording()
                logging.info('Stopped recording from Cros device.')

                # Gets the recorded data. This step is time consuming.
                playback_recorder.read_recorded_binary()
                logging.info('Read recorded binary from Chameleon.')
                record_recorder.read_recorded_binary()
                logging.info('Read recorded binary from Chameleon.')

        recorded_file = os.path.join(self.resultsdir, "playback_recorded.raw")
        logging.info('Playback: Saving recorded data to %s', recorded_file)
        playback_recorder.save_file(recorded_file)
        recorded_file = os.path.join(self.resultsdir, "record_recorded.raw")
        logging.info('Record: Saving recorded data to %s', recorded_file)
        record_recorder.save_file(recorded_file)

        # Removes the beginning of recorded data. This is to avoid artifact
        # caused by Chameleon codec initialization in the beginning of
        # recording.
        playback_recorder.remove_head(0.5)

        # Removes noise by a lowpass filter.
        playback_recorder.lowpass_filter(2500)
        recorded_file = os.path.join(self.resultsdir, "playback_filtered.raw")
        logging.info('Saving filtered data to %s', recorded_file)
        playback_recorder.save_file(recorded_file)
        record_recorder.lowpass_filter(2000)
        recorded_file = os.path.join(self.resultsdir, "record_filtered.raw")
        logging.info('Saving filtered data to %s', recorded_file)
        record_recorder.save_file(recorded_file)

        # Compares data by frequency. Audio signal recorded by microphone has
        # gone through analog processing and through the air.
        # This suffers from codec artifacts and noise on the path.
        # Comparing data by frequency is more robust than comparing by
        # correlation, which is suitable for fully-digital audio path like USB
        # and HDMI.
        error_messages = ''
        if not chameleon_audio_helper.compare_recorded_result(
                golden_file, playback_recorder, 'frequency'):
            error_messages += 'Record: Recorded file does not match playback file.'
        if not chameleon_audio_helper.compare_recorded_result(
                golden_file, record_recorder, 'frequency'):
            error_messages += 'Playback: Recorded file does not match playback file.'
        if error_messages:
            raise error.TestFail(error_messages)
