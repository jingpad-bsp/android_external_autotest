# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import shlex
import subprocess

from autotest_lib.client.cros.audio import cmd_utils

ARECORD_PATH='/usr/bin/arecord'
APLAY_PATH='/usr/bin/aplay'
AMIXER_PATH='/usr/bin/amixer'

def _get_format_args(channels, bits, rate):
    args = ['-c', str(channels)]
    args += ['-f', 'S%d_LE' % bits]
    args += ['-r', str(rate)]
    return args


def _get_default_device():
    return 'plughw:%d' % get_default_soundcard_id()


def playback(*args, **kargs):
    '''A helper funciton to execute playback_cmd.'''
    cmd_utils.execute(playback_cmd(*args, **kargs))


def playback_cmd(
        input, duration=None, channels=2, bits=16, rate=48000, device=None):
    '''Plays the given input audio by the ALSA utility: 'aplay'.

    @param input: The input audio to be played.
    @param duration: The length of the playback (in seconds).
    @param channels: The number of channels of the input audio.
    @param bits: The number of bits of each audio sample.
    @param rate: The sampling rate.
    @param device: The device to play the audio on.
    '''
    args = [APLAY_PATH]
    if duration is not None:
        args += ['-d', str(duration)]
    args += _get_format_args(channels, bits, rate)
    if device is None:
        device = _get_default_device()
    args += ['-D', device]
    args += [input]
    return args


def record(*args, **kargs):
    '''A helper function to execute record_cmd.'''
    cmd_utils.execute(record_cmd(*args, **kargs))


def record_cmd(
        output, duration=None, channels=1, bits=16, rate=48000, device=None):
    '''Records the audio to the specified output by ALSA utility: 'arecord'.

    @param output: The filename where the recorded audio will be stored to.
    @param duration: The length of the recording (in seconds).
    @param channels: The number of channels of the recorded audio.
    @param bits: The number of bits of each audio sample.
    @param rate: The sampling rate.
    @param device: The device used to recorded the audio from.
    '''
    args = [ARECORD_PATH]
    if duration is not None:
        args += ['-d', str(duration)]
    args += _get_format_args(channels, bits, rate)
    if device is None:
        device = _get_default_device()
    args += ['-D', device]
    args += [output]
    return args


_default_soundcard_id = -1

def get_default_soundcard_id():
    '''Gets the ID of the default soundcard.

    @raise RuntimeError: if it fails to find the default soundcard id.
    '''
    global _default_soundcard_id
    if _default_soundcard_id == -1:
        _default_soundcard_id = _find_default_soundcard_id()

    if _default_soundcard_id is None:
        raise RuntimeError('no soundcard found')
    return _default_soundcard_id


def _find_default_soundcard_id():
    '''Finds the id of the default hardware soundcard.'''

    # If there is only one card, choose it; otherwise,
    # choose the first card with controls named 'Speaker'
    cmd = 'amixer -c %d scontrols'
    id = 0
    while True:
        p = cmd_utils.popen(shlex.split(cmd % id), stdout=subprocess.PIPE)
        output, _ = p.communicate()
        if p.wait() != 0: # end of the card list
            break;
        if 'speaker' in output.lower():
            return id
        id = id + 1

    # If there is only one soundcard, return it, else return not found (None)
    return 0 if id == 1 else None

def dump_control_contents(device=None):
    if device is None:
        device = 'hw:%d' % get_default_soundcard_id()
    args = [AMIXER_PATH, '-D', device, 'contents']
    return cmd_utils.execute(args, stdout=subprocess.PIPE)
