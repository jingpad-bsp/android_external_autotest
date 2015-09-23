# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a server side test to check nodes created for internal card."""

import logging
import os
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.chameleon import audio_test_utils
from autotest_lib.client.cros.chameleon import chameleon_audio_ids
from autotest_lib.client.cros.chameleon import chameleon_audio_helper
from autotest_lib.server.cros.audio import audio_test
from autotest_lib.server.cros.multimedia import remote_facade_factory


class audio_InternalCardNodes(audio_test.AudioTest):
    """Server side test to check audio nodes for internal card.

    This test talks to a Chameleon board and a Cros device to verify
    audio nodes created for internal cards are correct.

    """
    version = 1
    DELAY_AFTER_PLUGGING = 2

    def run_once(self, host):
        chameleon_board = host.chameleon
        factory = remote_facade_factory.RemoteFacadeFactory(host)
        audio_facade = factory.create_audio_facade()

        chameleon_board.reset()

        jack_plugger = chameleon_board.get_audio_board().get_jack_plugger()

        expected_plugged_nodes_without_audio_jack = (
                ['INTERNAL_SPEAKER'],
                ['INTERNAL_MIC', 'POST_DSP_LOOPBACK',
                 'POST_MIX_LOOPBACK'])

        expected_plugged_nodes_with_audio_jack = (
                ['INTERNAL_SPEAKER', 'HEADPHONE'],
                ['INTERNAL_MIC', 'MIC', 'POST_DSP_LOOPBACK',
                 'POST_MIX_LOOPBACK'])

        # Modify expected nodes for special boards.
        board_name = host.get_board().split(':')[1]

        if board_name == 'link':
            expected_plugged_nodes_without_audio_jack[1].append('KEYBOARD_MIC')
            expected_plugged_nodes_with_audio_jack[1].append('KEYBOARD_MIC')

        if board_name == 'samus':
            expected_plugged_nodes_without_audio_jack[1].append('AOKR')
            expected_plugged_nodes_with_audio_jack[1].append('AOKR')

        audio_test_utils.check_plugged_nodes(
                audio_facade, expected_plugged_nodes_without_audio_jack)

        try:
            jack_plugger.plug()
            time.sleep(self.DELAY_AFTER_PLUGGING)

            audio_test_utils.check_plugged_nodes(
                    audio_facade, expected_plugged_nodes_with_audio_jack)

        finally:
            jack_plugger.unplug()

        audio_test_utils.check_plugged_nodes(
                audio_facade, expected_plugged_nodes_without_audio_jack)

