# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, utils, tempfile, os, shlex, subprocess

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.audio import audio_helper

_TEST_CLIENT = '/usr/bin/cras_test_client'
_DEFAULT_PLAYBACK_CONFIG = {'exec': _TEST_CLIENT,
                            'rate': '44100',
                            'buffer_frames': '512'}
_DEFAULT_RECORD_CONFIG = {'exec': _TEST_CLIENT,
                          'rate': '48000',
                          'buffer_frames': '512'}
_TEST_SAMPLE_RATES = [ '8000',
                       '16000',
                       '22050',
                       '32000',
                       '44100',
                       '48000',
                       '88200',
                       '96000',
                       '192000' ]
# Minimum RMS value to consider a "pass".  Can't be too high because we don't
# know how much or our recording will be silence waiting for the tone to start.
_MIN_SOX_RMS_VALUE = 0.05
# Input and output levels.
_TEST_VOLUME_LEVEL = 100
_TEST_CAPTURE_GAIN = 2500

class audiovideo_CRASFormatConversion(test.test):
    version = 1

    def initialize(self):
        """ Setup for the format conversion test.
        """
        # Set up the audio helper class.
        # Record command will have file name appended
        cmd_rec = ('%s --buffer_frames 441 --duration 2'
                   ' --rate 44100 --capture_file ' % _TEST_CLIENT)
        self._ah = audio_helper.AudioHelper(self,
                                            record_command = cmd_rec,
                                            sox_threshold = _MIN_SOX_RMS_VALUE)
        self._ah.setup_deps(['sox'])
        self._sox_min_rms = _MIN_SOX_RMS_VALUE
        super(audiovideo_CRASFormatConversion, self).initialize()

    def playback_command_from_config(self, config):
        return ('%(exec)s --playback_file %(file)s'
                ' --buffer_frames %(buffer_frames)s'
                ' --rate %(rate)s --duration 2' % config)

    def record_command_from_config(self, config):
        return ('%(exec)s --capture_file %(file)s'
                ' --buffer_frames %(buffer_frames)s'
                ' --rate %(rate)s --duration 1' % config)

    def play_two_freqs(self, playback_config, primary, secondary):
        """ Starts a stream at primary sample rate, adds a stream at secondary.
        Args:
            playback_config: configuraiton args for test client playback.
            primary: The sample rate to play first, HW will be set to this.
            secondary: The second sample rate, will be SRC'd to the first.

        """
        # Start with the primary sample rate, then add the secondary.  This
        # causes the secondary to be SRC'd to the primary rate.
        playback_config['rate'] = primary;
        cmd = self.playback_command_from_config(playback_config)
        logging.info(cmd)
        first = subprocess.Popen(shlex.split(cmd))

        playback_config['rate'] = secondary;
        cmd = self.playback_command_from_config(playback_config)
        logging.info(cmd)
        second = subprocess.Popen(shlex.split(cmd))

        first.wait();
        if first.returncode != 0:
            raise error.TestError('playback error %d' % first.returncode)

        second.wait();
        if second.returncode != 0:
            raise error.TestError('playback error %d' % second.returncode)

    # Record a sample stream at the given rate
    def run_capture_stream(self, record_config, rate):
        """ Captures audio at the given sample rate..
        Args:
            record_config: configuration args for test client record.
            rate: The sample rate to record at.
        """
        record_config['rate'] = rate;
        cmd = self.record_command_from_config(record_config)
        logging.info(cmd)
        record_proc = subprocess.Popen(shlex.split(cmd))
        record_proc.wait();

    def run_once(self):
        """Runs the format conversion test.
        """
        playback_config = _DEFAULT_PLAYBACK_CONFIG.copy()
        playback_config['file'] = os.path.join(self.bindir, 'sine.wav')
        record_config = _DEFAULT_RECORD_CONFIG.copy()
        record_config['file'] = '/tmp/cras_record.wav'

        self._ah.set_volume_levels(_TEST_VOLUME_LEVEL, _TEST_CAPTURE_GAIN)

        # Record silence to use as the noise profile.
        noise_file = tempfile.NamedTemporaryFile(mode='w+t');
        noise_config = record_config.copy()
        noise_config['file'] = noise_file.name
        cmd = self.record_command_from_config(noise_config)
        logging.info(cmd)
        noise_proc = subprocess.Popen(shlex.split(cmd))
        noise_proc.wait();

        # Try all sample rate pairs.
        for primary in _TEST_SAMPLE_RATES:
            for secondary in _TEST_SAMPLE_RATES:
                self._ah.loopback_test_channels(
                    noise_file.name,
                    lambda channel: self.play_two_freqs(playback_config, primary, secondary))

        # Record at all sample rates
        for rate in _TEST_SAMPLE_RATES:
            self.run_capture_stream(record_config, rate)
