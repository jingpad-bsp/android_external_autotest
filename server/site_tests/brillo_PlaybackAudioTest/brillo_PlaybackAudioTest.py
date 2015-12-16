# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

import common
from autotest_lib.client.common_lib.feedback import client
from autotest_lib.server import test


# The amount of time to wait when producing silence (i.e. no playback).
_SILENCE_DURATION_SECS = 5


class brillo_PlaybackAudioTest(test.test):
    """Verify that basic audio playback works."""
    version = 1

    def __init__(self, *args, **kwargs):
        super(brillo_PlaybackAudioTest, self).__init__(*args, **kwargs)
        self.host = None


    def test_playback(self, fb_query, playback_cmd):
        """Performs a playback test.

        @param fb_query: A feedback query.
        @param playback_cmd: The playback generating command, or None for no-op.
        """
        fb_query.prepare()
        if playback_cmd:
            self.host.run(playback_cmd)
        else:
            time.sleep(_SILENCE_DURATION_SECS)
        fb_query.validate()


    def run_once(self, host, fb_client):
        """Runs the test.

        @param host: A host object representing the DUT.
        @param fb_client: A feedback client implementation.
        """
        self.host = host
        with fb_client.initialize(self, host):
            logging.info('Testing silent playback')
            fb_query = fb_client.new_query(client.QUERY_AUDIO_PLAYBACK_SILENT)
            self.test_playback(fb_query, None)

            logging.info('Testing audible playback')
            fb_query = fb_client.new_query(client.QUERY_AUDIO_PLAYBACK_AUDIBLE)
            self.test_playback(fb_query, 'slesTest_sawtoothBufferQueue')
