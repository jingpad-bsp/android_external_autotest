#!/usr/bin/python
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re
import tempfile
import threading

from glob import glob

from autotest_lib.client.bin import utils
from autotest_lib.client.bin.input.input_device import *
from autotest_lib.client.common_lib import error

LD_LIBRARY_PATH = 'LD_LIBRARY_PATH'

_DEFAULT_NUM_CHANNELS = 2
_DEFAULT_REC_COMMAND = 'arecord -D hw:0,0 -d 10 -f dat'
_DEFAULT_SOX_FORMAT = '-t raw -b 16 -e signed -r 48000 -L'
_DEFAULT_SOX_RMS_THRESHOLD = 0.5

_JACK_VALUE_ON_RE = re.compile('.*values=on')
_HP_JACK_CONTROL_RE = re.compile('numid=(\d+).*Headphone\sJack')
_MIC_JACK_CONTROL_RE = re.compile('numid=(\d+).*Mic\sJack')

_SOX_RMS_AMPLITUDE_RE = re.compile('RMS\s+amplitude:\s+(.+)')
_SOX_ROUGH_FREQ_RE = re.compile('Rough\s+frequency:\s+(.+)')
_SOX_FORMAT = '-t raw -b 16 -e signed -r 48000 -L'

_AUDIO_NOT_FOUND_RE = r'Audio\snot\sdetected'
_MEASURED_LATENCY_RE = r'Measured\sLatency:\s(\d+)\suS'
_REPORTED_LATENCY_RE = r'Reported\sLatency:\s(\d+)\suS'

class RecordSampleThread(threading.Thread):
    '''Wraps the execution of arecord in a thread.'''
    def __init__(self, audio, recordfile):
        threading.Thread.__init__(self)
        self._audio = audio
        self._recordfile = recordfile

    def run(self):
        self._audio.record_sample(self._recordfile)


class AudioHelper(object):
    '''
    A helper class contains audio related utility functions.
    '''
    def __init__(self, test,
                 sox_format = _DEFAULT_SOX_FORMAT,
                 sox_threshold = _DEFAULT_SOX_RMS_THRESHOLD,
                 record_command = _DEFAULT_REC_COMMAND,
                 num_channels = _DEFAULT_NUM_CHANNELS):
        self._test = test
        self._sox_threshold = sox_threshold
        self._sox_format = sox_format
        self._rec_cmd = record_command
        self._num_channels = num_channels

    def setup_deps(self, deps):
        '''
        Sets up audio related dependencies.
        '''
        for dep in deps:
            if dep == 'test_tones':
                dep_dir = os.path.join(self._test.autodir, 'deps', dep)
                self._test.job.install_pkg(dep, 'dep', dep_dir)
                self.test_tones_path = os.path.join(dep_dir, 'src', dep)
            elif dep == 'audioloop':
                dep_dir = os.path.join(self._test.autodir, 'deps', dep)
                self._test.job.install_pkg(dep, 'dep', dep_dir)
                self.audioloop_path = os.path.join(dep_dir, 'src',
                        'looptest')
                self.loopback_latency_path = os.path.join(dep_dir, 'src',
                        'loopback_latency')
            elif dep == 'sox':
                dep_dir = os.path.join(self._test.autodir, 'deps', dep)
                self._test.job.install_pkg(dep, 'dep', dep_dir)
                self.sox_path = os.path.join(dep_dir, 'bin', dep)
                self.sox_lib_path = os.path.join(dep_dir, 'lib')
                if os.environ.has_key(LD_LIBRARY_PATH):
                    paths = os.environ[LD_LIBRARY_PATH].split(':')
                    if not self.sox_lib_path in paths:
                        paths.append(self.sox_lib_path)
                        os.environ[LD_LIBRARY_PATH] = ':'.join(paths)
                else:
                    os.environ[LD_LIBRARY_PATH] = self.sox_lib_path

    def cleanup_deps(self, deps):
        '''
        Cleans up environments which has been setup for dependencies.
        '''
        for dep in deps:
            if dep == 'sox':
                if (os.environ.has_key(LD_LIBRARY_PATH)
                        and hasattr(self, 'sox_lib_path')):
                    paths = filter(lambda x: x != self.sox_lib_path,
                            os.environ[LD_LIBRARY_PATH].split(':'))
                    os.environ[LD_LIBRARY_PATH] = ':'.join(paths)

    def set_volume_levels(self, volume, capture):
        '''
        Sets the volume and capture gain through cras_test_client
        '''
        logging.info('Setting volume level to %d' % volume)
        utils.system('/usr/bin/cras_test_client --volume %d' % volume)
        logging.info('Setting capture gain to %d' % capture)
        utils.system('/usr/bin/cras_test_client --capture_gain %d' % capture)
        utils.system('/usr/bin/cras_test_client --dump_server_info')
        utils.system('/usr/bin/cras_test_client --mute 0')
        utils.system('amixer -c 0 contents')

    def get_mixer_jack_status(self, jack_reg_exp):
        '''
        Gets the mixer jack status.

        Args:
            jack_reg_exp: The regular expression to match jack control name.

        Returns:
            None if the control does not exist, return True if jack control
            is detected plugged, return False otherwise.
        '''
        output = utils.system_output('amixer -c0 controls', retain_output=True)
        numid = None
        for line in output.split('\n'):
            m = jack_reg_exp.match(line)
            if m:
                numid = m.group(1)
                break

        # Proceed only when matched numid is not empty.
        if numid:
            output = utils.system_output('amixer -c0 cget numid=%s' % numid)
            for line in output.split('\n'):
                if _JACK_VALUE_ON_RE.match(line):
                    return True
            return False
        else:
            return None

    def get_hp_jack_status(self):
        status = self.get_mixer_jack_status(_HP_JACK_CONTROL_RE)
        if status is not None:
            return status

        # When headphone jack is not found in amixer, lookup input devices
        # instead.
        #
        # TODO(hychao): Check hp/mic jack status dynamically from evdev. And
        # possibly replace the existing check using amixer.
        for evdev in glob('/dev/input/event*'):
            device = InputDevice(evdev)
            if device.is_hp_jack():
                return device.get_headphone_insert()
        else:
            return None

    def get_mic_jack_status(self):
        status = self.get_mixer_jack_status(_MIC_JACK_CONTROL_RE)
        if status is not None:
            return status

        # When mic jack is not found in amixer, lookup input devices instead.
        for evdev in glob('/dev/input/event*'):
            device = InputDevice(evdev)
            if device.is_mic_jack():
                return device.get_microphone_insert()
        else:
            return None

    def check_loopback_dongle(self):
        '''
        Checks if loopback dongle is equipped correctly.
        '''
        # Check Mic Jack
        mic_jack_status = self.get_mic_jack_status()
        if mic_jack_status is None:
            logging.warning('Found no Mic Jack control, skip check.')
        elif not mic_jack_status:
            logging.info('Mic jack is not plugged.')
            return False
        else:
            logging.info('Mic jack is plugged.')

        # Check Headphone Jack
        hp_jack_status = self.get_hp_jack_status()
        if hp_jack_status is None:
            logging.warning('Found no Headphone Jack control, skip check.')
        elif not hp_jack_status:
            logging.info('Headphone jack is not plugged.')
            return False
        else:
            logging.info('Headphone jack is plugged.')

        # Use latency check to test if audio can be captured through dongle.
        # We only want to know the basic function of dongle, so no need to
        # assert the latency accuracy here.
        latency = self.loopback_latency_check(n=4000)
        if latency:
            logging.info('Got latency measured %d, reported %d' %
                    (latency[0], latency[1]))
        else:
            logging.warning('Latency check fail.')
            return False

        return True

    def set_mixer_controls(self, mixer_settings={}, card='0'):
        '''
        Sets all mixer controls listed in the mixer settings on card.
        '''
        logging.info('Setting mixer control values on %s' % card)
        for item in mixer_settings:
            logging.info('Setting %s to %s on card %s' %
                         (item['name'], item['value'], card))
            cmd = 'amixer -c %s cset name=%s %s'
            cmd = cmd % (card, item['name'], item['value'])
            try:
                utils.system(cmd)
            except error.CmdError:
                # A card is allowed not to support all the controls, so don't
                # fail the test here if we get an error.
                logging.info('amixer command failed: %s' % cmd)

    def sox_stat_output(self, infile, channel):
        sox_mixer_cmd = self.get_sox_mixer_cmd(infile, channel)
        stat_cmd = '%s -c 1 %s - -n stat 2>&1' % (self.sox_path,
                self._sox_format)
        sox_cmd = '%s | %s' % (sox_mixer_cmd, stat_cmd)
        return utils.system_output(sox_cmd, retain_output=True)

    def get_audio_rms(self, sox_output):
        for rms_line in sox_output.split('\n'):
            m = _SOX_RMS_AMPLITUDE_RE.match(rms_line)
            if m is not None:
                return float(m.group(1))

    def get_rough_freq(self, sox_output):
        for rms_line in sox_output.split('\n'):
            m = _SOX_ROUGH_FREQ_RE.match(rms_line)
            if m is not None:
                return int(m.group(1))


    def get_sox_mixer_cmd(self, infile, channel):
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

        return '%s -c 2 %s %s -c 1 %s - mixer %s' % (self.sox_path,
                self._sox_format, infile, self._sox_format, pan_values)

    def noise_reduce_file(self, in_file, noise_file, out_file):
        '''Runs the sox command to noise-reduce in_file using
           the noise profile from noise_file.

        Args:
            in_file: The file to noise reduce.
            noise_file: The file containing the noise profile.
                        This can be created by recording silence.
            out_file: The file contains the noise reduced sound.

        Returns:
            The name of the file containing the noise-reduced data.
        '''
        prof_cmd = '%s -c 2 %s %s -n noiseprof' % (self.sox_path,
                _SOX_FORMAT, noise_file)
        reduce_cmd = ('%s -c 2 %s %s -c 2 %s %s noisered' %
                (self.sox_path, _SOX_FORMAT, in_file, _SOX_FORMAT, out_file))
        utils.system('%s | %s' % (prof_cmd, reduce_cmd))

    def record_sample(self, tmpfile):
        '''Records a sample from the default input device.

        Args:
            duration: How long to record in seconds.
            tmpfile: The file to record to.
        '''
        cmd_rec = self._rec_cmd + ' %s' % tmpfile
        logging.info('Command %s recording now' % cmd_rec)
        utils.system(cmd_rec)

    def loopback_test_channels(self, noise_file, loopback_callback,
                               check_recorded_callback=None):
        '''Tests loopback on all channels.

        Args:
            noise_file: The file contains the pre-recorded noise.
            loopback_callback: The callback to do the loopback for one channel.
        '''
        for channel in xrange(self._num_channels):
            # Temp file for the final noise-reduced file.
            with tempfile.NamedTemporaryFile(mode='w+t') as reduced_file:
                # Temp file that records before noise reduction.
                with tempfile.NamedTemporaryFile(mode='w+t') as tmpfile:
                    record_thread = RecordSampleThread(self, tmpfile.name)
                    record_thread.start()
                    loopback_callback(channel)
                    record_thread.join()

                    self.noise_reduce_file(tmpfile.name, noise_file.name,
                            reduced_file.name)

                sox_output = self.sox_stat_output(reduced_file.name, channel)

                # Use injected check recorded callback if any.
                if check_recorded_callback:
                    check_recorded_callback(sox_output)
                else:
                    self.check_recorded(sox_output)

    def check_recorded(self, sox_output):
        """Checks if the calculated RMS value is expected.

        Args:
            sox_output: The output from sox stat command.

        Raises:
            error.TestFail if the RMS amplitude of the recording isn't above
                the threshold.
        """
        rms_val = self.get_audio_rms(sox_output)

        # In case we don't get a valid RMS value.
        if rms_val is None:
            raise error.TestError(
                'Failed to generate an audio RMS value from playback.')

        logging.info('Got audio RMS value of %f. Minimum pass is %f.' %
                     (rms_val, self._sox_threshold))
        if rms_val < self._sox_threshold:
            raise error.TestError(
                'Audio RMS value %f too low. Minimum pass is %f.' %
                (rms_val, self._sox_threshold))

    def loopback_latency_check(self, **args):
        '''
        Checks loopback latency.

        Args:
            args: additional arguments for loopback_latency.

        Returns:
            A tuple containing measured and reported latency in uS.
            Return None if no audio detected.
        '''
        noise_threshold = str(args['n']) if args.has_key('n') else '400'

        cmd = '%s -n %s' % (self.loopback_latency_path, noise_threshold)

        output = utils.system_output(cmd)
        measured_latency = None
        reported_latency = None
        for line in output.split('\n'):
            match = re.search(_MEASURED_LATENCY_RE, line, re.I)
            if match:
                measured_latency = int(match.group(1))
                continue
            match = re.search(_REPORTED_LATENCY_RE, line, re.I)
            if match:
                reported_latency = int(match.group(1))
                continue
            if re.search(_AUDIO_NOT_FOUND_RE, line, re.I):
                return None
        if measured_latency and reported_latency:
            return (measured_latency, reported_latency)
        else:
            # Should not reach here, just in case.
            return None

    def play_sound(self, duration_seconds=None, audio_file_path=None):
        '''
        Plays a sound file found at |audio_file_path| for |duration_seconds|.

        If |audio_file_path|=None, plays a default audio file.
        If |duration_seconds|=None, plays audio file in its entirety.
        '''
        if not audio_file_path:
            audio_file_path = '/usr/local/autotest/cros/audio/sine440.wav'
        duration_arg = ('-d %d' % duration_seconds) if duration_seconds else ''
        utils.system('aplay %s %s' % (duration_arg, audio_file_path))

    def get_play_sine_args(self, channel, odev='default', freq=1000, duration=10,
            sample_size=16):
        '''Gets the command args to generate a sine wav to play to odev.

        Args:
          channel: 0 for left, 1 for right; otherwize, mono.
          odev: alsa output device.
          freq: frequency of the generated sine tone.
          duration: duration of the generated sine tone.
          sample_size: output audio sample size. Default to 16.
        '''
        cmdargs = [self.sox_path, '-b', str(sample_size), '-n', '-t', 'alsa',
                   odev, 'synth', str(duration)]
        if channel == 0:
            cmdargs += ['sine', str(freq), 'sine', '0']
        elif channel == 1:
            cmdargs += ['sine', '0', 'sine', str(freq)]
        else:
            cmdargs += ['sine', str(freq)]

        return cmdargs

    def play_sine(self, channel, odev='default', freq=1000, duration=10,
            sample_size=16):
        '''Generates a sine wave and plays to odev.'''
        cmdargs = self.get_play_sine_args(channel, odev, freq, duration, sample_size)
        utils.system(' '.join(cmdargs))
