# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a server side audio nodes s test using the Chameleon board."""

import logging
import time

from autotest_lib.client.cros.chameleon import audio_test_utils
from autotest_lib.client.cros.chameleon import audio_widget_link
from autotest_lib.client.cros.chameleon import chameleon_audio_ids
from autotest_lib.server.cros.audio import audio_test
from autotest_lib.server.cros.multimedia import remote_facade_factory



class audio_AudioNodeSwitch(audio_test.AudioTest):
    """Server side audio test.

    This test talks to a Chameleon board and a Cros device to verify
    audio nodes switch correctly.

    """
    version = 1
    _PLUG_DELAY = 5

    def run_once(self, host, jack_node=False):
        chameleon_board = host.chameleon
        audio_board = chameleon_board.get_audio_board()
        factory = remote_facade_factory.RemoteFacadeFactory(host)

        chameleon_board.reset()
        audio_facade = factory.create_audio_facade()

        audio_test_utils.check_audio_nodes(audio_facade,
                                           (['INTERNAL_SPEAKER'],
                                            ['INTERNAL_MIC']))
        if jack_node:
            jack_plugger = audio_board.get_jack_plugger()
            jack_plugger.plug()
            time.sleep(self._PLUG_DELAY)
            audio_test_utils.check_audio_nodes(audio_facade,
                                               (['HEADPHONE'], ['MIC']))
            jack_plugger.unplug()
        time.sleep(self._PLUG_DELAY)
        audio_test_utils.check_audio_nodes(audio_facade,
                                           (['INTERNAL_SPEAKER'],
                                            ['INTERNAL_MIC']))