# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.cros.audio import audio_helper
from autotest_lib.client.cros import cros_ui_test, httpd
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import power_suspend, sys_power

_DEFAULT_NUM_CHANNELS = 2
_DEFAULT_RECORD_DURATION = 5
_DEFAULT_VOLUME_LEVEL = 100
_DEFAULT_CAPTURE_GAIN = 2500
# Minimum RMS value to pass when checking recorded file.
_DEFAULT_SOX_RMS_THRESHOLD = 0.08
_DEFAULT_SUSPEND_DURATION = 5
_DEFAULT_ITERATIONS = 2000

class audio_SuspendResumeStress(cros_ui_test.UITest):
    """Verifies audio output after suspend/resume stress test."""
    version = 1

    def initialize(self,
                   num_channels=_DEFAULT_NUM_CHANNELS,
                   record_duration=_DEFAULT_RECORD_DURATION,
                   volume_level=_DEFAULT_VOLUME_LEVEL,
                   capture_gain=_DEFAULT_CAPTURE_GAIN):
        """Setup the deps for the test.

        @param num_channels: The number of channels on the device to test.
        @param record_duration: How long of a sample to record.

        @raises error.TestError if the deps can't be run.
        """
        self._volume_level = volume_level
        self._capture_gain = capture_gain

        cmd_rec = 'arecord -d %f -f dat' % record_duration
        self._ah = audio_helper.AudioHelper(self,
                record_command=cmd_rec,
                num_channels=num_channels)
        self._suspender = power_suspend.Suspender(self.resultsdir,
                                                  method=sys_power.do_suspend)

        super(audio_SuspendResumeStress, self).initialize('$default')
        self._test_url = 'http://localhost:8000/play.html'
        self._testServer = httpd.HTTPListener(8000, docroot=self.bindir)
        self._testServer.run()

    def run_once(self):
        """Entry point of this test."""
        self._ah.set_volume_levels(self._volume_level, self._capture_gain)
        if not self._ah.check_loopback_dongle():
            raise error.TestError('Audio loopback dongle is in bad state.')

        # Record a sample of "silence" to use as a noise profile.
        noise_file_name = self._ah.create_wav_file("noise")
        self._ah.record_sample(noise_file_name)

        # Play the same video to test all channels.
        for _ in xrange(_DEFAULT_ITERATIONS):
            logging.info('Start %s audio verification before suspend.' % _)
            self.play_media()
            self._ah.loopback_test_channels(noise_file_name, None,
                                            lambda x:self.check_recorded(x, _),
                                            preserve_test_file=False)
            logging.info('End %s audio verification before suspend.' % _)
            logging.info('Start %s suspend/resume.' % _)
            self._suspender.suspend(_DEFAULT_SUSPEND_DURATION)
            logging.info('End %s suspend/resume.' % _)
            logging.info('Start %s audio verification after suspend.' % _)
            self.play_media()
            self._ah.loopback_test_channels(noise_file_name, None,
                                            lambda x:self.check_recorded(x, _),
                                            preserve_test_file=False)
            logging.info('End %s audio verification after suspend.' % _)

    def play_media(self):
        """Plays a media file in Chromium.
        """
        logging.info('Playing mp3 file infinite.')
        self.pyauto.NavigateToURL(self._test_url)

    def check_recorded(self, sox_output, test_iteration):
        """Checks if the calculated RMS value is expected.

        @param sox_output: The output from sox stat command.
        @param test_iteration: The iteration during the test failed.

        @raises error.TestError if RMS amplitude can't be parsed.
                the threshold.
        """
        rms_val = self._ah.get_audio_rms(sox_output)

        # In case we don't get a valid RMS value.
        if rms_val is None:
            raise error.TestError(
                'Failed to generate an audio RMS value from playback.')

        logging.info('Got audio RMS value of %f. Minimum pass is %f.',
                      rms_val, _DEFAULT_SOX_RMS_THRESHOLD)
        if rms_val < _DEFAULT_SOX_RMS_THRESHOLD:
            raise error.TestFail(
                ('Audio RMS value %f too low. Minimum pass is %f.'
                 'Test iteration: %s.') %
                (rms_val, _DEFAULT_SOX_RMS_THRESHOLD, test_iteration))
