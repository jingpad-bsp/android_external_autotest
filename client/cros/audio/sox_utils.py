# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

SOX_PATH = '/usr/local/bin/sox'

def generate_sine_tone_cmd(
        filename, channels=2, bits=16, rate=44100, duration=None, frequence=440,
        gain=None):
    """Gets a command to generate sine tones at specified ferquencies.

    @param filename: the name of the file to store the sine wave in.
    @param channels: the number of channels.
    @param bits: the number of bits of each sample.
    @param rate: the sampling rate.
    @param duration: the length of the generated sine tone (in seconds).
    @param frequence: the frequence of the sine wave.
    @param gain: the gain (in db).
    """
    args = [SOX_PATH, '-n', '-t', 'raw']
    args += ['-c', str(channels)]
    args += ['-b', str(bits)]
    args += ['-r', str(rate)]
    args.append(filename)
    args.append('synth')
    if duration is not None:
        args.append(str(duration))
    args += ['sine', str(frequence)]
    if gain is not None:
        args += ['gain', str(gain)]
    return args
