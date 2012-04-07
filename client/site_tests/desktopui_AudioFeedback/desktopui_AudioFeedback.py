# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, threading, tempfile

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, httpd
from autotest_lib.client.cros.audio import audio_helper

# Names of mixer controls.
_CONTROL_MASTER = "'Master Playback Volume'"
_CONTROL_HEADPHONE = "'Headphone Playback Volume'"
_CONTROL_SPEAKER = "'Speaker Playback Volume'"
_CONTROL_SPEAKER_HP = "'HP/Speakers'"
_CONTROL_MIC_BOOST = "'Mic Boost Volume'"
_CONTROL_CAPTURE = "'Capture Volume'"
_CONTROL_PCM = "'PCM Playback Volume'"
_CONTROL_DIGITAL = "'Digital Capture Volume'"
_CONTROL_CAPTURE_SWITCH = "'Capture Switch'"

# Default test configuration.
_DEFAULT_CARD = '0'
_DEFAULT_MIXER_SETTINGS = [{'name': _CONTROL_MASTER, 'value': "100%"},
                           {'name': _CONTROL_HEADPHONE, 'value': "100%"},
                           {'name': _CONTROL_MIC_BOOST, 'value': "50%"},
                           {'name': _CONTROL_PCM, 'value': "100%"},
                           {'name': _CONTROL_DIGITAL, 'value': "100%"},
                           {'name': _CONTROL_CAPTURE, 'value': "100%"},
                           {'name': _CONTROL_CAPTURE_SWITCH, 'value': "on"}]

_CONTROL_SPEAKER_DEVICE = ['x86-alex', 'x86-mario', 'x86-zgb']
_CONTROL_SPEAKER_DEVICE_HP = ['stumpy', 'lumpy']

_DEFAULT_NUM_CHANNELS = 2
_DEFAULT_RECORD_DURATION = 15
# Minimum RMS value to consider a "pass".
_DEFAULT_SOX_RMS_THRESHOLD = 0.30


class RecordSampleThread(threading.Thread):
    """Wraps the execution of arecord in a thread."""
    def __init__(self, audio, duration, recordfile):
        threading.Thread.__init__(self)
        self._audio = audio
        self._duration = duration
        self._recordfile = recordfile

    def run(self):
        self._audio.record_sample(self._duration, self._recordfile)


class desktopui_AudioFeedback(cros_ui_test.UITest):
    version = 1

    def initialize(self,
                   card=_DEFAULT_CARD,
                   mixer_settings=_DEFAULT_MIXER_SETTINGS,
                   num_channels=_DEFAULT_NUM_CHANNELS,
                   record_duration=_DEFAULT_RECORD_DURATION,
                   sox_min_rms=_DEFAULT_SOX_RMS_THRESHOLD):
        """Setup the deps for the test.

        Args:
            card: The index of the sound card to use.
            mixer_settings: Alsa control settings to apply to the mixer before
                starting the test.
            num_channels: The number of channels on the device to test.
            record_duration: How long of a sample to record.
            sox_min_rms: The minimum RMS value to consider a pass.

        Raises:
            error.TestError if the deps can't be run.
        """
        self._card = card
        self._mixer_settings = mixer_settings
        self._num_channels = num_channels
        self._record_duration = record_duration
        self._sox_min_rms = sox_min_rms

        self._ah = audio_helper.AudioHelper(self)
        self._ah.setup_deps(['sox'])

        super(desktopui_AudioFeedback, self).initialize()
        self._test_url = 'http://localhost:8000/youtube.html'
        self._testServer = httpd.HTTPListener(8000, docroot=self.bindir)
        self._testServer.run()

    def run_once(self):
        # Speaker control settings may differ from device to device.
        if self.pyauto.ChromeOSBoard() in _CONTROL_SPEAKER_DEVICE:
            self._mixer_settings.append({'name': _CONTROL_SPEAKER,
                                         'value': "0%"})
        elif self.pyauto.ChromeOSBoard() in _CONTROL_SPEAKER_DEVICE_HP:
            self._mixer_settings.append({'name': _CONTROL_SPEAKER_HP,
                                         'value': "0%"})
        self._ah.set_mixer_controls(self._mixer_settings, self._card)

        # Record a sample of "silence" to use as a noise profile.
        with tempfile.NamedTemporaryFile(mode='w+t') as noise_file:
            logging.info('Noise file: %s' % noise_file.name)
            self._ah.record_sample(1, noise_file.name)

            # Test each channel separately. Assume two channels.
            for channel in xrange(0, self._num_channels):
                self.loopback_test_one_channel(channel, noise_file.name)

    def play_video(self):
        """Plays a Youtube video to record audio samples.

           Skipping initial 60 seconds so we can ignore initial silence
           in the video.
        """
        logging.info('Playing back youtube media file %s.' % self._test_url)
        self.pyauto.NavigateToURL(self._test_url)
        if not self.pyauto.WaitUntil(lambda: self.pyauto.ExecuteJavascript("""
                    player_status = document.getElementById('player_status');
                    window.domAutomationController.send(player_status.innerHTML);
               """), expect_retval='player ready'):
            raise error.TestError('Failed to load the Youtube player')
        self.pyauto.ExecuteJavascript("""
            ytplayer.pauseVideo();
            ytplayer.seekTo(60, true);
            ytplayer.playVideo();
            window.domAutomationController.send('');
        """)

    def loopback_test_one_channel(self, channel, noise_file):
        """Test loopback for a given channel.

        Args:
            channel: The channel to test loopback on.
            noise_file: Noise profile to use for filtering, None to skip noise
                filtering.
        """
        with tempfile.NamedTemporaryFile(mode='w+t') as reduced_file:
            with tempfile.NamedTemporaryFile(mode='w+t') as tmpfile:
                record_thread = RecordSampleThread(self._ah,
                        self._record_duration, tmpfile.name)
                self.play_video()
                record_thread.start()
                record_thread.join()

                self._ah.noise_reduce_file(tmpfile.name, noise_file,
                        reduced_file.name)
            self.check_recorded_audio(reduced_file.name, channel)

    def check_recorded_audio(self, infile, channel):
        """Runs the sox command to check if we captured audio.

        Note: if we captured any sufficient loud audio which can generate
        the rms_value greater than the threshold value, test will pass.
        TODO (rohitbm) : find a way to compare the recorded audio with
                         an actual sample file.

        Args:
            infile: The file is to test for (strong) audio content via the RMS
                    method.
            channel: The audio channel to test.

        Raises:
            error.TestFail if the RMS amplitude of the recording isn't above
                the threshold.
        """
        rms_val = self._ah.get_audio_rms(infile, channel)
        # In case sox didn't return an RMS value.
        if rms_val is None:
            raise error.TestError(
                'Failed to generate an audio RMS value from playback.')

        logging.info('Got audio RMS value of %f. Minimum pass is %f.' %
                     (rms_val, self._sox_min_rms))
        if rms_val < self._sox_min_rms:
                raise error.TestError(
                    'Audio RMS value %f too low. Minimum pass is %f.' %
                    (rms_val, self._sox_min_rms))
