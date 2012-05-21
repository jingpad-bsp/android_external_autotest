# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, utils, tempfile

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.audio import audio_helper

# Names of mixer controls
_CONTROL_MASTER = "'Master Playback Volume'"
_CONTROL_HEADPHONE = "'Headphone Playback Volume'"
_CONTROL_SPEAKER = "'Speaker Playback Volume'"
_CONTROL_MIC_BOOST = "'Mic Boost Volume'"
_CONTROL_MIC_CAPTURE = "'Mic Capture Volume'"
_CONTROL_CAPTURE = "'Capture Volume'"
_CONTROL_PCM = "'PCM Playback Volume'"
_CONTROL_DIGITAL = "'Digital Capture Volume'"
_CONTROL_CAPTURE_SWITCH = "'Capture Switch'"

# Default test configuration.
_DEFAULT_TONE_CONFIG = {'type': 'tone',
                        'frequency': 1000,
                        'tone_length_sec': 1.0,
                        'tone_volume': 1.0,
                        'channels': 2,
                        'active_channel': None,
                        'alsa_device': 'default'}
_DEFAULT_CARD = '0'
_DEFAULT_FREQUENCY = 1000
_DEFAULT_MIXER_SETTINGS = [{'name':_CONTROL_MASTER, 'value': "100%"},
                           {'name':_CONTROL_HEADPHONE, 'value': "100%"},
                           {'name':_CONTROL_SPEAKER, 'value': "0%"},
                           {'name':_CONTROL_MIC_BOOST, 'value': "50%"},
                           {'name':_CONTROL_MIC_CAPTURE, 'value': "50%"},
                           {'name':_CONTROL_PCM, 'value':"100%"},
                           {'name':_CONTROL_DIGITAL, 'value':"100%"},
                           {'name':_CONTROL_CAPTURE, 'value':"100%"},
                           {'name':_CONTROL_CAPTURE_SWITCH, 'value':"on"}]
_DEFAULT_NUM_CHANNELS = 2
_DEFAULT_RECORD_DURATION = 1
# Minimum RMS value to consider a "pass".  Can't be too high because we don't
# know how much or our recording will be silence waiting for the tone to start.
_DEFAULT_SOX_RMS_THRESHOLD = 0.5

_DEFAULT_INPUT = 'default'
_DEFAULT_OUTPUT = 'default'


class audiovideo_LineOutToMicInLoopback(test.test):
    version = 1

    def initialize(self,
                   card=_DEFAULT_CARD,
                   frequency=_DEFAULT_FREQUENCY,
                   input=_DEFAULT_INPUT,
                   mixer_settings=_DEFAULT_MIXER_SETTINGS,
                   num_channels=_DEFAULT_NUM_CHANNELS,
                   output=_DEFAULT_OUTPUT,
                   record_duration=_DEFAULT_RECORD_DURATION,
                   sox_min_rms=_DEFAULT_SOX_RMS_THRESHOLD):
        """ Setup the deps for the test.

        Args:
            card: The index of the sound card to use.
            frequency: The frequency of the test tone that is looped back.
            input: The input device to capture audio from.
            mixer_settings: Alsa control settings to apply to the mixer before
                starting the test.
            num_channels: The number of channels on the device to test.
            output: The output device to play audio to.
            record_duration: How long of a sample to record.
            sox_min_rms: The minimum RMS value to consider a pass.

        Raises: error.TestError if the deps can't be run
        """
        self._card = card
        self._frequency = frequency
        self._mixer_settings = mixer_settings
        self._num_channels = num_channels
        self._output = output
        self._record_duration = record_duration
        self._sox_min_rms = sox_min_rms

        self._ah = audio_helper.AudioHelper(self, input_device=input,
                record_duration=record_duration,
                num_channels=num_channels)
        self._ah.setup_deps(['sox', 'test_tones'])

        super(audiovideo_LineOutToMicInLoopback, self).initialize()

    def run_once(self):
        """Runs the loopback test.
        """
        self._ah.set_mixer_controls(self._mixer_settings, self._card)

        # Record a sample of "silence" to use as a noise profile.
        with tempfile.NamedTemporaryFile(mode='w+t') as noise_file:
            logging.info('Noise file: %s' % noise_file.name)
            self._ah.record_sample(noise_file.name)

            self._ah.loopback_test_channels(noise_file,
                    self.loopback_test_one_channel,
                    self.check_recorded_audio)


    def loopback_test_one_channel(self, channel):
        """Test loopback for a given channel.

        Args:
            channel: The channel to test loopback on.
        """
        config = _DEFAULT_TONE_CONFIG.copy()
        config['tone_length_sec'] = self._record_duration
        config['active_channel'] = '%d' % channel
        config['frequency'] = self._frequency
        config['alsa_device'] = self._output

        self.run_test_tones(config)


    def run_test_tones(self, args):
        """Runs the tone generator executable.

        Args:
            args: A hash listing the parameters for test_tones.
                  Required keys:
                    exec - Executable to run
                    type - 'scale' or 'tone'
                    frequency - float with frequency in Hz.
                    tone_length_sec - float with length of test tone in secs.
                    tone_volume - float with volume to do tone (0 to 1.0)
                    channels - number of channels in output device.

                  Optional keys:
                    active_channel: integer to select channel for playback.
                                    None means playback on all channels.
        """
        args['exec'] = self._ah.test_tones_path

        if not 'tone_end_volume' in args:
            args['tone_end_volume'] = args['tone_volume']

        cmd = ('%(exec)s '
               '-t %(type)s -h %(frequency)f -l %(tone_length_sec)f '
               '-c %(channels)d -s %(tone_volume)f '
               '-e %(tone_end_volume)f' % args)
        if args['active_channel'] is not None:
            cmd += ' -a %s' % args['active_channel']
        if args['type'] == 'tone':
            logging.info('[tone %dHz]' % args['frequency'])
        if args['alsa_device'] is not None:
            cmd += ' -d %s' % args['alsa_device']
        elif args['type'] == 'scale':
            logging.info('[A# harmonic minor scale]')
        logging.info(cmd)
        utils.system(cmd)


    def check_recorded_audio(self, sox_output):
        """Checks if the calculated RMS value is expected.

        Args:
            sox_output: The output from sox stat command.

        Raises:
            error.TestFail if the RMS amplitude of the recording isn't above
                the threshold.
        """
        rms_val = self._ah.get_audio_rms(sox_output)
        logging.info('Got RMS value of %f' % rms_val)
        if rms_val < self._sox_min_rms:
            raise error.TestError( 'RMS value %f too low.' % rms_val)
