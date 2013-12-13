# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import tempfile

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.audio import audio_helper
from autotest_lib.client.cros.audio import cmd_utils
from autotest_lib.client.cros.audio import cras_utils
from autotest_lib.client.cros.audio import sox_utils

TEST_DURATION = 5 # In seconds.
PLAYER_TIMEOUT = 5 # In seconds.
VOLUME_LEVEL = 100
CAPTURE_GAIN = 2500

# Media formats to be tested. The length of these audio are all 5 seconds.
MEDIA_FORMATS = ['sine440.mp3',
                 'sine440.mp4',
                 'sine440.wav',
                 'sine440.ogv',
                 'sine440.webm']

class desktopui_MediaAudioFeedback(test.test):
    """Verifies if media playback can be captured."""

    version = 1

    @audio_helper.chrome_rms_test
    def run_once(self, chrome):
        noise_file = os.path.join(self.resultsdir, 'noise.wav')
        noiseprof_file = tempfile.NamedTemporaryFile()

        # Record a sample of "silence" to use as a noise profile.
        cras_utils.capture(noise_file, duration=2)
        sox_utils.noise_profile(noise_file, noiseprof_file.name)

        # Open the test page
        chrome.browser.SetHTTPServerDirectories(self.bindir)
        tab = chrome.browser.tabs[0]
        tab.Navigate(chrome.browser.http_server.UrlOf(
                os.path.join(self.bindir, 'play.html')))
        tab.WaitForDocumentReadyStateToBeComplete()

        # Test each media file for all channels.
        for media_file in MEDIA_FORMATS:
            self.rms_test(tab, media_file, noiseprof_file.name)

        os.unlink(noise_file)


    def rms_test(self, tab, media_file, noiseprof_file):
        logging.info('rms test on media file %s.', media_file)
        recorded_file = os.path.join(self.resultsdir, 'recorded.wav')
        loopback_file = os.path.join(self.resultsdir, 'loopback.wav')

        # Plays the media_file in the browser.
        self.play_media(tab, media_file)

        # Record the audio output and also the CRAS loopback output.
        p1 = cmd_utils.popen(cras_utils.capture_cmd(
                recorded_file, duration=TEST_DURATION))
        p2 = cmd_utils.popen(cras_utils.loopback_cmd(
                loopback_file, duration=TEST_DURATION))
        cmd_utils.wait_and_check_returncode(p1, p2)

        # See if we recorded something.

        # We captured two channels of audio in the CRAS loopback.
        # The RMS values are for debugging only.
        loopback_stats = [audio_helper.get_channel_sox_stat(
                loopback_file, i) for i in (1, 2)]
        logging.info('loopback stats: %s', [str(s) for s in loopback_stats])

        reduced_file = tempfile.NamedTemporaryFile()
        sox_utils.noise_reduce(
                recorded_file, reduced_file.name, noiseprof_file)
        audio_helper.check_rms(reduced_file.name)

        # Make sure the audio can be played to the end.
        self.wait_player_end(tab)

        # Keep these files if the test failed.
        os.unlink(recorded_file)
        os.unlink(loopback_file)


    def wait_player_end(self, tab):
        """Wait for player ends playing."""
        utils.poll_for_condition(
            condition=lambda: tab.EvaluateJavaScript('player.ended'),
            exception=error.TestError('Player never end until timeout.'),
            timeout=PLAYER_TIMEOUT)


    def play_media(self, tab, media_file):
        """Plays a media file in Chromium.

        @param media_file: Media file to test.
        """
        tab.EvaluateJavaScript('play("%s")' % media_file)

        def get_current_time():
            return tab.EvaluateJavaScript('player.currentTime')

        # Make sure the audio is being played
        old_time = get_current_time()
        utils.poll_for_condition(
            condition=lambda: get_current_time() > old_time,
            exception=error.TestError('Player never start until timeout.'),
            timeout=PLAYER_TIMEOUT)
