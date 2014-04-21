#!/usr/bin/python
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import pipes
import re
import shlex
import tempfile
import threading
import time

from glob import glob
from autotest_lib.client.bin import test, utils
from autotest_lib.client.bin.input.input_device import *
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.audio import alsa_utils
from autotest_lib.client.cros.audio import cmd_utils
from autotest_lib.client.cros.audio import cras_utils
from autotest_lib.client.cros.audio import sox_utils

LD_LIBRARY_PATH = 'LD_LIBRARY_PATH'

_AUDIO_DIAGNOSTICS_PATH = '/usr/bin/audio_diagnostics'

_DEFAULT_NUM_CHANNELS = 2
_DEFAULT_REC_COMMAND = 'arecord -D hw:0,0 -d 10 -f dat'
_DEFAULT_SOX_FORMAT = '-t raw -b 16 -e signed -r 48000 -L'
_DEFAULT_PLAYBACK_VOLUME = 100
_DEFAULT_CAPTURE_GAIN = 2500

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

def log_loopback_dongle_status():
    '''
    Log the status of the loopback dongle to make sure it is equipped correctly.
    '''
    dongle_status_ok = True

    # Check Mic Jack
    mic_jack_status = get_mic_jack_status()
    logging.info('Mic jack status: %s', mic_jack_status)
    dongle_status_ok &= bool(mic_jack_status)

    # Check Headphone Jack
    hp_jack_status = get_hp_jack_status()
    logging.info('Headphone jack status: %s', hp_jack_status)
    dongle_status_ok &= bool(hp_jack_status)

    # Use latency check to test if audio can be captured through dongle.
    # We only want to know the basic function of dongle, so no need to
    # assert the latency accuracy here.
    latency = loopback_latency_check(n=4000)
    if latency:
        logging.info('Got latency measured %d, reported %d',
                latency[0], latency[1])
    else:
        logging.info('Latency check fail.')
        dongle_status_ok = False

    logging.info('audio loopback dongle test: %s',
            'PASS' if dongle_status_ok else 'FAIL')

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

def record_sample(tmpfile, record_command=_DEFAULT_REC_COMMAND):
    '''Records a sample from the default input device.

    @param tmpfile: The file to record to.
    @param record_command: The command to record audio.
    '''
    utils.system('%s %s' % (record_command, tmpfile))

def create_wav_file(wav_dir, prefix=""):
    '''Creates a unique name for wav file.

    The created file name will be preserved in autotest result directory
    for future analysis.

    @param prefix: specified file name prefix.
    '''
    filename = "%s-%s.wav" % (prefix, time.time())
    return os.path.join(wav_dir, filename)

def run_in_parallel(*funs):
    threads = []
    for f in funs:
        t = threading.Thread(target=f)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

def loopback_test_channels(noise_file_name, wav_dir,
                           playback_callback=None,
                           check_recorded_callback=check_audio_rms,
                           preserve_test_file=True,
                           num_channels = _DEFAULT_NUM_CHANNELS,
                           record_callback=record_sample,
                           mix_callback=None):
    '''Tests loopback on all channels.

    @param noise_file_name: Name of the file contains pre-recorded noise.
    @param playback_callback: The callback to do the playback for
        one channel.
    @param record_callback: The callback to do the recording.
    @param check_recorded_callback: The callback to check recorded file.
    @param preserve_test_file: Retain the recorded files for future debugging.
    '''
    for channel in xrange(num_channels):
        record_file_name = create_wav_file(wav_dir,
                                           "record-%d" % channel)
        functions = [lambda: record_callback(record_file_name)]

        if playback_callback:
            functions.append(lambda: playback_callback(channel))

        if mix_callback:
            mix_file_name = create_wav_file(wav_dir, "mix-%d" % channel)
            functions.append(lambda: mix_callback(mix_file_name))

        run_in_parallel(*functions)

        if mix_callback:
            sox_output_mix = sox_stat_output(mix_file_name, channel)
            rms_val_mix = get_audio_rms(sox_output_mix)
            logging.info('Got mixed audio RMS value of %f.', rms_val_mix)

        sox_output_record = sox_stat_output(record_file_name, channel)
        rms_val_record = get_audio_rms(sox_output_record)
        logging.info('Got recorded audio RMS value of %f.', rms_val_record)

        reduced_file_name = create_wav_file(wav_dir,
                                            "reduced-%d" % channel)
        noise_reduce_file(record_file_name, noise_file_name,
                          reduced_file_name)

        sox_output_reduced = sox_stat_output(reduced_file_name, channel)

        if not preserve_test_file:
            os.unlink(reduced_file_name)
            os.unlink(record_file_name)
            if mix_callback:
                os.unlink(mix_file_name)

        check_recorded_callback(sox_output_reduced)


def get_channel_sox_stat(
        input_audio, channel_index, channels=2, bits=16, rate=48000):
    """Gets the sox stat info of the selected channel in the input audio file.

    @param input_audio: The input audio file to be analyzed.
    @param channel_index: The index of the channel to be analyzed.
                          (1 for the first channel).
    @param channels: The number of channels in the input audio.
    @param bits: The number of bits of each audio sample.
    @param rate: The sampling rate.
    """
    if channel_index <= 0 or channel_index > channels:
        raise ValueError('incorrect channel_indexi: %d' % channel_index)

    if channels == 1:
        return sox_utils.get_stat(
                input_audio, channels=channels, bits=bits, rate=rate)

    p1 = cmd_utils.popen(
            sox_utils.extract_channel_cmd(
                    input_audio, '-', channel_index,
                    channels=channels, bits=bits, rate=rate),
            stdout=cmd_utils.PIPE)
    p2 = cmd_utils.popen(
            sox_utils.stat_cmd('-', channels=1, bits=bits, rate=rate),
            stdin=p1.stdout, stderr=cmd_utils.PIPE)
    stat_output = p2.stderr.read()
    cmd_utils.wait_and_check_returncode(p1, p2)
    return sox_utils.parse_stat_output(stat_output)


def get_rms(input_audio, channels=1, bits=16, rate=48000):
    """Gets the RMS values of all channels of the input audio.

    @param input_audio: The input audio file to be checked.
    @param channels: The number of channels in the input audio.
    @param bits: The number of bits of each audio sample.
    @param rate: The sampling rate.
    """
    stats = [get_channel_sox_stat(
            input_audio, i + 1, channels=channels, bits=bits,
            rate=rate) for i in xrange(channels)]

    logging.info('sox stat: %s', [str(s) for s in stats])
    return [s.rms for s in stats]


def reduce_noise_and_get_rms(
        input_audio, noise_file, channels=1, bits=16, rate=48000):
    """Reduces noise in the input audio by the given noise file and then gets
    the RMS values of all channels of the input audio.

    @param input_audio: The input audio file to be analyzed.
    @param noise_file: The noise file used to reduce noise in the input audio.
    @param channels: The number of channels in the input audio.
    @param bits: The number of bits of each audio sample.
    @param rate: The sampling rate.
    """
    with tempfile.NamedTemporaryFile() as reduced_file:
        p1 = cmd_utils.popen(
                sox_utils.noise_profile_cmd(
                        noise_file, '-', channels=channels, bits=bits,
                        rate=rate),
                stdout=cmd_utils.PIPE)
        p2 = cmd_utils.popen(
                sox_utils.noise_reduce_cmd(
                        input_audio, reduced_file.name, '-',
                        channels=channels, bits=bits, rate=rate),
                stdin=p1.stdout)
        cmd_utils.wait_and_check_returncode(p1, p2)
        return get_rms(reduced_file.name, channels, bits, rate)


def skip_devices_to_test(*boards):
    """Devices to skip due to hardware or test compatibility issues."""
    # TODO(scottz): Remove this when crbug.com/220147 is fixed.
    dut_board = utils.get_current_board()
    if dut_board in boards:
       raise error.TestNAError('This test is not available on %s' % dut_board)


def cras_rms_test_setup():
    """ Setups for the cras_rms_tests.

    To make sure the line_out-to-mic_in path is all green.
    """
    # TODO(owenlin): Now, the nodes are choosed by chrome.
    #                We should do it here.
    output_node, _ = cras_utils.get_selected_nodes()

    cras_utils.set_system_volume(_DEFAULT_PLAYBACK_VOLUME)
    cras_utils.set_node_volume(output_node, _DEFAULT_PLAYBACK_VOLUME)

    cras_utils.set_capture_gain(_DEFAULT_CAPTURE_GAIN)

    cras_utils.set_system_mute(False)
    cras_utils.set_capture_mute(False)


def generate_rms_postmortem():
    try:
        logging.info('audio postmortem report')
        log_loopback_dongle_status()
        logging.info(cmd_utils.execute(
                [_AUDIO_DIAGNOSTICS_PATH], stdout=cmd_utils.PIPE))
    except Exception:
        logging.exception('Error while generating postmortem report')


class _base_rms_test(test.test):
    """ Base class for all rms_test """

    def postprocess(self):
        super(_base_rms_test, self).postprocess()

        # Sum up the number of failed constraints in each iteration
        if sum(len(x) for x in self.failed_constraints):
            generate_rms_postmortem()


class chrome_rms_test(_base_rms_test):
    """ Base test class for audio RMS test with Chrome.

    The chrome instance can be accessed by self.chrome.
    """
    def warmup(self):
        skip_devices_to_test('x86-mario')
        super(chrome_rms_test, self).warmup()

        # Not all client of this file using telemetry.
        # Just do the import here for those who really need it.
        from autotest_lib.client.common_lib.cros import chrome

        self.chrome = chrome.Chrome()

        # The audio configuration could be changed when we
        # restart chrome.
        try:
            cras_rms_test_setup()
        except Exception:
            self.chrome.browser.Close()
            raise


    def cleanup(self, *args):
        try:
            self.chrome.browser.Close()
        finally:
            super(chrome_rms_test, self).cleanup()

class cras_rms_test(_base_rms_test):
    """ Base test class for CRAS audio RMS test."""

    def warmup(self):
        skip_devices_to_test('x86-mario')
        super(cras_rms_test, self).warmup()
        cras_rms_test_setup()


class alsa_rms_test(_base_rms_test):
    """ Base test class for ALSA audio RMS test."""

    def warmup(self):
        skip_devices_to_test('x86-mario')
        super(alsa_rms_test, self).warmup()

        # TODO(owenlin): Don't use CRAS for setup.
        cras_rms_test_setup()

        # CRAS does not apply the volume and capture gain to ALSA util
        # streams are added. Do that to ensure the values have been set.
        cras_utils.playback('/dev/zero', duration=0.1)
        cras_utils.capture('/dev/null', duration=0.1)
