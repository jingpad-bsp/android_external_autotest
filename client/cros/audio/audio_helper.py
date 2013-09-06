#!/usr/bin/python
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re
import threading
import time

from glob import glob

from autotest_lib.client.bin import utils
from autotest_lib.client.bin.input.input_device import *
from autotest_lib.client.common_lib import error

LD_LIBRARY_PATH = 'LD_LIBRARY_PATH'

_DEFAULT_NUM_CHANNELS = 2
_DEFAULT_REC_COMMAND = 'arecord -D hw:0,0 -d 10 -f dat'
_DEFAULT_SOX_FORMAT = '-t raw -b 16 -e signed -r 48000 -L'

# Minimum RMS value to pass when checking recorded file.
_DEFAULT_SOX_RMS_THRESHOLD = 0.08

_JACK_VALUE_ON_RE = re.compile('.*values=on')
_HP_JACK_CONTROL_RE = re.compile('numid=(\d+).*Headphone\sJack')
_MIC_JACK_CONTROL_RE = re.compile('numid=(\d+).*Mic\sJack')

_SOX_RMS_AMPLITUDE_RE = re.compile('RMS\s+amplitude:\s+(.+)')
_SOX_ROUGH_FREQ_RE = re.compile('Rough\s+frequency:\s+(.+)')

_AUDIO_NOT_FOUND_RE = r'Audio\snot\sdetected'
_MEASURED_LATENCY_RE = r'Measured\sLatency:\s(\d+)\suS'
_REPORTED_LATENCY_RE = r'Reported\sLatency:\s(\d+)\suS'

# Tools from platform/audiotest
AUDIOFUNTEST_PATH = 'audiofuntest'
AUDIOLOOP_PATH = 'looptest'
LOOPBACK_LATENCY_PATH = 'loopback_latency'
SOX_PATH = 'sox'
TEST_TONES_PATH = 'test_tones'


def set_mixer_controls(mixer_settings={}, card='0'):
    '''
    Sets all mixer controls listed in the mixer settings on card.

    @param mixer_settings: Mixer settings to set.
    @param card: Index of audio card to set mixer settings for.
    '''
    logging.info('Setting mixer control values on %s', card)
    for item in mixer_settings:
        logging.info('Setting %s to %s on card %s',
                     item['name'], item['value'], card)
        cmd = 'amixer -c %s cset name=%s %s'
        cmd = cmd % (card, item['name'], item['value'])
        try:
            utils.system(cmd)
        except error.CmdError:
            # A card is allowed not to support all the controls, so don't
            # fail the test here if we get an error.
            logging.info('amixer command failed: %s', cmd)

def set_volume_levels(volume, capture):
    '''
    Sets the volume and capture gain through cras_test_client

    @param volume: The playback volume to set.
    @param capture: The capture gain to set.
    '''
    logging.info('Setting volume level to %d', volume)
    utils.system('/usr/bin/cras_test_client --volume %d' % volume)
    logging.info('Setting capture gain to %d', capture)
    utils.system('/usr/bin/cras_test_client --capture_gain %d' % capture)
    utils.system('/usr/bin/cras_test_client --dump_server_info')
    utils.system('/usr/bin/cras_test_client --mute 0')
    utils.system('amixer -c 0 contents')

def loopback_latency_check(**args):
    '''
    Checks loopback latency.

    @param args: additional arguments for loopback_latency.

    @return A tuple containing measured and reported latency in uS.
        Return None if no audio detected.
    '''
    noise_threshold = str(args['n']) if args.has_key('n') else '400'

    cmd = '%s -n %s' % (LOOPBACK_LATENCY_PATH, noise_threshold)

    output = utils.system_output(cmd, retain_output=True)

    # Sleep for a short while to make sure device is not busy anymore
    # after called loopback_latency.
    time.sleep(.1)

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

def get_mixer_jack_status(jack_reg_exp):
    '''
    Gets the mixer jack status.

    @param jack_reg_exp: The regular expression to match jack control name.

    @return None if the control does not exist, return True if jack control
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

def get_hp_jack_status():
    '''Gets the status of headphone jack'''
    status = get_mixer_jack_status(_HP_JACK_CONTROL_RE)
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

def get_mic_jack_status():
    '''Gets the status of mic jack'''
    status = get_mixer_jack_status(_MIC_JACK_CONTROL_RE)
    if status is not None:
        return status

    # When mic jack is not found in amixer, lookup input devices instead.
    for evdev in glob('/dev/input/event*'):
        device = InputDevice(evdev)
        if device.is_mic_jack():
            return device.get_microphone_insert()
    else:
        return None

def check_loopback_dongle():
    '''
    Checks if loopback dongle is equipped correctly.
    '''
    # Check Mic Jack
    mic_jack_status = get_mic_jack_status()
    if mic_jack_status is None:
        logging.warning('Found no Mic Jack control, skip check.')
    elif not mic_jack_status:
        logging.info('Mic jack is not plugged.')
        return False
    else:
        logging.info('Mic jack is plugged.')

    # Check Headphone Jack
    hp_jack_status = get_hp_jack_status()
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
    latency = loopback_latency_check(n=4000)
    if latency:
        logging.info('Got latency measured %d, reported %d',
                latency[0], latency[1])
    else:
        logging.warning('Latency check fail.')
        return False

    return True

# Functions to test audio palyback.
def play_sound(duration_seconds=None, audio_file_path=None):
    '''
    Plays a sound file found at |audio_file_path| for |duration_seconds|.

    If |audio_file_path|=None, plays a default audio file.
    If |duration_seconds|=None, plays audio file in its entirety.

    @param duration_seconds: Duration to play sound.
    @param audio_file_path: Path to the audio file.
    '''
    if not audio_file_path:
        audio_file_path = '/usr/local/autotest/cros/audio/sine440.wav'
    duration_arg = ('-d %d' % duration_seconds) if duration_seconds else ''
    utils.system('aplay %s %s' % (duration_arg, audio_file_path))

def get_play_sine_args(channel, odev='default', freq=1000, duration=10,
                       sample_size=16):
    '''Gets the command args to generate a sine wav to play to odev.

    @param channel: 0 for left, 1 for right; otherwize, mono.
    @param odev: alsa output device.
    @param freq: frequency of the generated sine tone.
    @param duration: duration of the generated sine tone.
    @param sample_size: output audio sample size. Default to 16.
    '''
    cmdargs = [SOX_PATH, '-b', str(sample_size), '-n', '-t', 'alsa',
               odev, 'synth', str(duration)]
    if channel == 0:
        cmdargs += ['sine', str(freq), 'sine', '0']
    elif channel == 1:
        cmdargs += ['sine', '0', 'sine', str(freq)]
    else:
        cmdargs += ['sine', str(freq)]

    return cmdargs

def play_sine(channel, odev='default', freq=1000, duration=10,
              sample_size=16):
    '''Generates a sine wave and plays to odev.

    @param channel: 0 for left, 1 for right; otherwize, mono.
    @param odev: alsa output device.
    @param freq: frequency of the generated sine tone.
    @param duration: duration of the generated sine tone.
    @param sample_size: output audio sample size. Default to 16.
    '''
    cmdargs = get_play_sine_args(channel, odev, freq, duration, sample_size)
    utils.system(' '.join(cmdargs))

# Functions to compose customized sox command, execute it and process the
# output of sox command.
def get_sox_mixer_cmd(infile, channel,
                      num_channels=_DEFAULT_NUM_CHANNELS,
                      sox_format=_DEFAULT_SOX_FORMAT):
    '''Gets sox mixer command to reduce channel.

    @param infile: Input file name.
    @param channel: The selected channel to take effect.
    @param num_channels: The number of total channels to test.
    @param sox_format: Format to generate sox command.
    '''
    # Build up a pan value string for the sox command.
    if channel == 0:
        pan_values = '1'
    else:
        pan_values = '0'
    for pan_index in range(1, num_channels):
        if channel == pan_index:
            pan_values = '%s%s' % (pan_values, ',1')
        else:
            pan_values = '%s%s' % (pan_values, ',0')

    return '%s -c 2 %s %s -c 1 %s - mixer %s' % (SOX_PATH,
            sox_format, infile, sox_format, pan_values)

def sox_stat_output(infile, channel,
                    num_channels=_DEFAULT_NUM_CHANNELS,
                    sox_format=_DEFAULT_SOX_FORMAT):
    '''Executes sox stat command.

    @param infile: Input file name.
    @param channel: The selected channel.
    @param num_channels: The number of total channels to test.
    @param sox_format: Format to generate sox command.

    @return The output of sox stat command
    '''
    sox_mixer_cmd = get_sox_mixer_cmd(infile, channel,
                                      num_channels, sox_format)
    stat_cmd = '%s -c 1 %s - -n stat 2>&1' % (SOX_PATH, sox_format)
    sox_cmd = '%s | %s' % (sox_mixer_cmd, stat_cmd)
    return utils.system_output(sox_cmd, retain_output=True)

def get_audio_rms(sox_output):
    '''Gets the audio RMS value from sox stat output

    @param sox_output: Output of sox stat command.

    @return The RMS value parsed from sox stat output.
    '''
    for rms_line in sox_output.split('\n'):
        m = _SOX_RMS_AMPLITUDE_RE.match(rms_line)
        if m is not None:
            return float(m.group(1))

def get_rough_freq(sox_output):
    '''Gets the rough audio frequency from sox stat output

    @param sox_output: Output of sox stat command.

    @return The rough frequency value parsed from sox stat output.
    '''
    for rms_line in sox_output.split('\n'):
        m = _SOX_ROUGH_FREQ_RE.match(rms_line)
        if m is not None:
            return int(m.group(1))

def check_audio_rms(sox_output, sox_threshold=_DEFAULT_SOX_RMS_THRESHOLD):
    """Checks if the calculated RMS value is expected.

    @param sox_output: The output from sox stat command.
    @param sox_threshold: The threshold to test RMS value against.

    @raises error.TestError if RMS amplitude can't be parsed.
    @raises error.TestFail if the RMS amplitude of the recording isn't above
            the threshold.
    """
    rms_val = get_audio_rms(sox_output)

    # In case we don't get a valid RMS value.
    if rms_val is None:
        raise error.TestError(
            'Failed to generate an audio RMS value from playback.')

    logging.info('Got audio RMS value of %f. Minimum pass is %f.',
                 rms_val, sox_threshold)
    if rms_val < sox_threshold:
        raise error.TestFail(
            'Audio RMS value %f too low. Minimum pass is %f.' %
            (rms_val, sox_threshold))

def noise_reduce_file(in_file, noise_file, out_file,
                      sox_format=_DEFAULT_SOX_FORMAT):
    '''Runs the sox command to noise-reduce in_file using
       the noise profile from noise_file.

    @param in_file: The file to noise reduce.
    @param noise_file: The file containing the noise profile.
        This can be created by recording silence.
    @param out_file: The file contains the noise reduced sound.
    @param sox_format: The  sox format to generate sox command.
    '''
    prof_cmd = '%s -c 2 %s %s -n noiseprof' % (SOX_PATH,
               sox_format, noise_file)
    reduce_cmd = ('%s -c 2 %s %s -c 2 %s %s noisered' %
            (SOX_PATH, sox_format, in_file, sox_format, out_file))
    utils.system('%s | %s' % (prof_cmd, reduce_cmd))


class RecordSampleThread(threading.Thread):
    '''Wraps the execution of arecord in a thread.'''
    def __init__(self, audio, recordfile):
        threading.Thread.__init__(self)
        self._audio = audio
        self._recordfile = recordfile

    def run(self):
        self._audio.record_sample(self._recordfile)


class RecordMixThread(threading.Thread):
    '''
    Wraps the execution of recording the mixed loopback stream in
    cras_test_client in a thread.
    '''
    def __init__(self, audio, recordfile):
        threading.Thread.__init__(self)
        self._audio = audio
        self._recordfile = recordfile

    def run(self):
        self._audio.record_mix(self._recordfile)


class AudioHelper(object):
    '''
    A helper class contains audio related utility functions.
    '''
    def __init__(self, test,
                 record_command = _DEFAULT_REC_COMMAND,
                 num_channels = _DEFAULT_NUM_CHANNELS,
                 mix_command = None):
        self._test = test
        self._rec_cmd = record_command
        self._num_channels = num_channels
        self._mix_cmd = mix_command

    def record_sample(self, tmpfile):
        '''Records a sample from the default input device.

        @param tmpfile: The file to record to.
        '''
        cmd_rec = self._rec_cmd + ' %s' % tmpfile
        logging.info('Command %s recording now', cmd_rec)
        utils.system(cmd_rec)

    def record_mix(self, tmpfile):
        '''Records a sample from the mixed loopback stream in cras_test_client.

        @param tmpfile: The file to record to.
        '''
        cmd_mix = self._mix_cmd + ' %s' % tmpfile
        logging.info('Command %s recording now', cmd_mix)
        utils.system(cmd_mix)

    def loopback_test_channels(self, noise_file_name,
                               loopback_callback=None,
                               check_recorded_callback=check_audio_rms,
                               preserve_test_file=True):
        '''Tests loopback on all channels.

        @param noise_file_name: Name of the file contains pre-recorded noise.
        @param loopback_callback: The callback to do the loopback for
            one channel.
        @param check_recorded_callback: The callback to check recorded file.
        @param preserve_test_file: Retain the recorded files for future debugging.
        '''
        for channel in xrange(self._num_channels):
            reduced_file_name = self.create_wav_file("reduced-%d" % channel)
            record_file_name = self.create_wav_file("record-%d" % channel)
            record_thread = RecordSampleThread(self, record_file_name)
            record_thread.start()

            if self._mix_cmd != None:
                mix_file_name = self.create_wav_file("mix-%d" % channel)
                mix_thread = RecordMixThread(self, mix_file_name)
                mix_thread.start()

            if loopback_callback:
                loopback_callback(channel)

            if self._mix_cmd != None:
                mix_thread.join()
                sox_output_mix = sox_stat_output(mix_file_name, channel)
                rms_val_mix = get_audio_rms(sox_output_mix)
                logging.info('Got mixed audio RMS value of %f.', rms_val_mix)

            record_thread.join()
            sox_output_record = sox_stat_output(record_file_name, channel)
            rms_val_record = get_audio_rms(sox_output_record)
            logging.info('Got recorded audio RMS value of %f.', rms_val_record)

            noise_reduce_file(record_file_name, noise_file_name,
                              reduced_file_name)

            sox_output_reduced = sox_stat_output(reduced_file_name,
                                                 channel)

            if not preserve_test_file:
                os.unlink(reduced_file_name)
                os.unlink(record_file_name)
                if self._mix_cmd != None:
                    os.unlink(mix_file_name)

            check_recorded_callback(sox_output_reduced)

    def create_wav_file(self, prefix=""):
        '''Creates a unique name for wav file.

        The created file name will be preserved in autotest result directory
        for future analysis.

        @param prefix: specified file name prefix.
        '''
        filename = "%s-%s.wav" % (prefix, time.time())
        return os.path.join(self._test.resultsdir, filename)
