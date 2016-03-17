# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a server side HDMI audio test using the Chameleon board."""

import logging
import os
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.audio import audio_test_data
from autotest_lib.client.cros.chameleon import audio_test_utils
from autotest_lib.client.cros.chameleon import chameleon_audio_helper
from autotest_lib.client.cros.chameleon import chameleon_audio_ids
from autotest_lib.server.cros.audio import audio_test


class audio_AudioBasicHDMI(audio_test.AudioTest):
    """Server side HDMI audio test.

    This test talks to a Chameleon board and a Cros device to verify
    HDMI audio function of the Cros device.

    """
    version = 2
    DELAY_BEFORE_PLAYBACK = 2
    DELAY_AFTER_PLAYBACK = 2

    def cleanup(self):
        """Restore the CPU scaling governor mode."""
        self._system_facade.set_scaling_governor_mode(0, self._original_mode)
        logging.debug('Set CPU0 mode to %s', self._original_mode)


    def set_high_performance_mode(self):
        """Set the CPU scaling governor mode to performance mode."""
        self._original_mode = self._system_facade.set_scaling_governor_mode(
                0, 'performance')
        logging.debug('Set CPU0 scaling governor mode to performance, '
                      'original_mode: %s', self._original_mode)


    def run_once(self, host):
        golden_file = audio_test_data.SWEEP_TEST_FILE

        # Dump audio diagnostics data for debugging.
        chameleon_board = host.chameleon
        factory = self.create_remote_facade_factory(host)

        # For DUTs with permanently connected audio jack cable
        # connecting HDMI won't switch automatically the node. Adding
        # audio_jack_plugged flag to select HDMI node after binding.
        audio_facade = factory.create_audio_facade()
        output_nodes, _ = audio_facade.get_selected_node_types()
        audio_jack_plugged = False
        if output_nodes == ['HEADPHONE']:
            audio_jack_plugged = True
            logging.debug('Found audio jack plugged!')

        self._system_facade = factory.create_system_facade()
        self.set_high_performance_mode()

        chameleon_board.setup_and_reset(self.outputdir)

        widget_factory = chameleon_audio_helper.AudioWidgetFactory(
                factory, host)

        source = widget_factory.create_widget(
            chameleon_audio_ids.CrosIds.HDMI)
        recorder = widget_factory.create_widget(
            chameleon_audio_ids.ChameleonIds.HDMI)
        binder = widget_factory.create_binder(source, recorder)

        with chameleon_audio_helper.bind_widgets(binder):
            audio_test_utils.dump_cros_audio_logs(
                    host, audio_facade, self.resultsdir, 'after_binding')

            # HDMI node needs to be selected, when audio jack is plugged
            if audio_jack_plugged:
                audio_facade.set_chrome_active_node_type('HDMI', None)

            audio_test_utils.check_audio_nodes(audio_facade,
                                               (['HDMI'], None))

            # Transfer the data to Cros device first because it takes
            # several seconds.
            source.set_playback_data(golden_file)

            logging.info('Start recording from Chameleon.')
            recorder.start_recording()

            time.sleep(self.DELAY_BEFORE_PLAYBACK)

            logging.info('Start playing %s on Cros device',
                         golden_file.path)
            source.start_playback(blocking=True)

            logging.info('Stopped playing %s on Cros device',
                         golden_file.path)
            time.sleep(self.DELAY_AFTER_PLAYBACK)

            audio_test_utils.dump_cros_audio_logs(
                    host, audio_facade, self.resultsdir, 'after_recording')

            recorder.stop_recording()
            logging.info('Stopped recording from Chameleon.')
            recorder.read_recorded_binary()

            recorded_file = os.path.join(self.resultsdir, "recorded.raw")
            logging.info('Saving recorded data to %s', recorded_file)
            recorder.save_file(recorded_file)

            if not chameleon_audio_helper.compare_recorded_result(
                    golden_file, recorder, 'correlation'):
                raise error.TestFail(
                        'Recorded file does not match playback file')
