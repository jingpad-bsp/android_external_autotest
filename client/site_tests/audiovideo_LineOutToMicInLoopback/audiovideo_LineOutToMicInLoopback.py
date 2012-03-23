# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, threading, utils

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

# Names of mixer controls
_CONTROL_MASTER = "'Master Playback Volume'"
_CONTROL_HEADPHONE = "'Headphone Playback Volume'"
_CONTROL_SPEAKER = "'Speaker Playback Volume'"
_CONTROL_MIC_BOOST = "'Mic Boost Volume'"
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
                           {'name':_CONTROL_PCM, 'value':"100%"},
                           {'name':_CONTROL_DIGITAL, 'value':"100%"},
                           {'name':_CONTROL_CAPTURE, 'value':"100%"},
                           {'name':_CONTROL_CAPTURE_SWITCH, 'value':"on"}]
_DEFAULT_NUM_CHANNELS = 2
_DEFAULT_RECORD_DURATION = 1
# Minimum RMS value to consider a "pass".  Can't be too high because we don't
# know how much or our recording will be silence waiting for the tone to start.
_DEFAULT_SOX_RMS_THRESHOLD = 0.5

# Regexp parsing sox output.
_SOX_RMS_AMPLITUDE_RE = re.compile('RMS\s+amplitude:\s+(.+)')
# Format used in sox commands.
_SOX_FORMAT = '-t raw -b 16 -e signed -r 48000 -L'

_DEFAULT_INPUT = 'default'
_DEFAULT_OUTPUT = 'default'

class RecordSampleThread(threading.Thread):
    """Wraps the running of arecord in a thread."""
    def __init__(self, audio, duration, recordfile):
        threading.Thread.__init__(self)
        self.audio = audio
        self.duration = duration
        self.recordfile = recordfile

    def run(self):
        self.audio.record_sample(self.duration, self.recordfile)


class audiovideo_LineOutToMicInLoopback(test.test):
    version = 1

    def setup(self):
        self.job.setup_dep(['test_tones'])
        self.job.setup_dep(['sox'])


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
        self._input = input
        self._mixer_settings = mixer_settings
        self._num_channels = num_channels
        self._output = output
        self._record_duration = record_duration
        self._sox_min_rms = sox_min_rms
        dep = 'test_tones'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)
        self._test_tones_path = os.path.join(dep_dir, 'src', dep)
        if not (os.path.exists(self._test_tones_path) and
                os.access(self._test_tones_path, os.X_OK)):
            raise error.TestError(
                    '%s is not an executable' % self._test_tones_path)

        dep = 'sox'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)
        self._sox_path = os.path.join(dep_dir, 'bin', dep)
        self._sox_lib_path = os.path.join(dep_dir, 'lib')
        if not (os.path.exists(self._sox_path) and
                os.access(self._sox_path, os.X_OK)):
            raise error.TestError(
                    '%s is not an executable' % self._sox_path)

        super(audiovideo_LineOutToMicInLoopback, self).initialize()


    def run_once(self):
        self.do_loopback_test()


    def do_loopback_test(self):
        """Runs the loopback test.
        """
        self.set_mixer_controls()
        # Record a sample of "silence" to use as a noise profile.
        noise_file = os.path.join(self.tmpdir, os.tmpnam())
        logging.info('Noise file: %s' % noise_file)
        self.record_sample(1, noise_file)

        try:
            # Test each channel separately. Assume two channels.
            for channel in xrange(0, self._num_channels):
                self.loopback_test_one_channel(channel, noise_file)
        finally:
            if os.path.isfile(noise_file):
                os.unlink(noise_file)


    def loopback_test_one_channel(self, channel, noise_file):
        """Test loopback for a given channel.

        Args:
            channel: The channel to test loopback on.
            noise_file: Noise profile to use for filtering, None to skip noise
                filtering.
        """
        config = _DEFAULT_TONE_CONFIG.copy()
        config['tone_length_sec'] = self._record_duration
        config['active_channel'] = '%d' % channel
        config['frequency'] = self._frequency
        config['alsa_device'] = self._output

        tmpfile = os.path.join(self.tmpdir, os.tmpnam())
        record_thread = RecordSampleThread(self, self._record_duration, tmpfile)
        record_thread.start()
        self.run_test_tones(config)
        record_thread.join()

        if noise_file is not None:
            test_file = self.noise_reduce_file(tmpfile, noise_file)
            os.unlink(tmpfile)
        else:
            test_file = tmpfile

        try:
            self.check_recorded_audio(test_file, channel)
        finally:
            if os.path.isfile(test_file):
                os.unlink(test_file)


    def record_sample(self, duration, tmpfile):
        """Records a sample from the default input device.

        Args:
            duration: How long to record in seconds.
            tmpfile: The file to record to.
        """
        cmd_rec = 'arecord -D %s -d %f -f dat %s' % (self._input,
                duration, tmpfile)
        logging.info('Command %s recording now (%fs)' % (cmd_rec, duration))
        utils.system(cmd_rec)


    def set_mixer_controls(self):
        """Sets all mixer controls listed in the mixer settings on card.
        """
        logging.info('Setting mixer control values on %s' % self._card)
        for item in self._mixer_settings:
            logging.info('Setting %s to %s on card %s' %
                         (item['name'], item['value'], self._card))
            cmd = 'amixer -c %s cset name=%s %s'
            cmd = cmd % (self._card, item['name'], item['value'])
            try:
                utils.system(cmd)
            except error.CmdError:
                # A card is allowed not to support all the controls, so don't
                # fail the test here if we get an error.
                logging.info('amixer command failed: %s' % cmd)

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
        args['exec'] = self._test_tones_path

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


    def check_recorded_audio(self, infile, channel):
        """ Runs the sox command to check if we captured audio.

        Args:
            infile: The file to test for audio in.
            channel: The audio channel to test.

        Raises:
            error.TestFail if the RMS amplitude of the recording isn't above
                the threshold.
        """
        # Build up a pan value string for the sox command.
        if channel == 0:
            pan_values = '1'
        else:
            pan_values = '0'
        for pan_index in range(1, self._num_channels):
            if channel == pan_index:
                pan_values = '%s%s' % (pan_values, ',1')
            else:
                pan_values = '%s%s' % (pan_values, ',0')
        # Set up the sox commands.
        os.environ["LD_LIBRARY_PATH"] = self._sox_lib_path
        sox_mixer_cmd = '%s -c 2 %s %s -c 1 %s - mixer %s'
        sox_mixer_cmd = sox_mixer_cmd % (self._sox_path, _SOX_FORMAT, infile,
                                         _SOX_FORMAT, pan_values)
        stat_cmd = '%s -c 1 %s - -n stat 2>&1' % (self._sox_path, _SOX_FORMAT)
        sox_cmd = '%s | %s' % (sox_mixer_cmd, stat_cmd)
        logging.info('running %s' % sox_cmd)
        sox_output = utils.system_output(sox_cmd, retain_output=True)
        # Find the RMS value line and check that it is above threshold.
        for rms_line in sox_output.split('\n'):
            m = _SOX_RMS_AMPLITUDE_RE.match(rms_line)
            if m is not None:
                rms_val = float(m.group(1))
                logging.info('Got RMS value of %f' % rms_val)
                if rms_val < self._sox_min_rms:
                    raise error.TestError( 'RMS value %f too low.' % rms_val)


    def noise_reduce_file(self, test_file, noise_file):
        """ Runs the sox command to noise-reduce test_file using
            the noise profile from noise_file.

        Args:
            test_file: The file to noise reduce.
            noise_file: The file containing the noise profile.
                        This can be created by recording silence.

        Returns:
            The name of the file containing the noise-reduced data.
        """
        out_file = os.path.join(self.tmpdir, os.tmpnam())
        os.environ["LD_LIBRARY_PATH"] = self._sox_lib_path
        prof_cmd = '%s -c 2 %s %s -n noiseprof' % (self._sox_path,
                                                           _SOX_FORMAT,
                                                           noise_file)
        reduce_cmd = ('%s -c 2 %s %s -c 2 %s %s noisered' %
                          (self._sox_path, _SOX_FORMAT, test_file, _SOX_FORMAT,
                           out_file))
        utils.system('%s | %s' % (prof_cmd, reduce_cmd))
        return out_file
