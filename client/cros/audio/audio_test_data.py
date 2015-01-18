#!/usr/bin/env python
# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides audio test data."""

import os


class AudioTestDataException(Exception):
    """Exception for audio test data."""
    pass


class AudioTestData(object):
    """Class to represent audio test data."""
    def __init__(self, data_format=None, path=None):
        """
        Initializes an audio test file.

        @param data_format: A dict containing data format including
                            file_type, sample_format, channel, and rate.
                            file_type: file type e.g. 'raw' or 'wav'.
                            sample_format: One of the keys in
                                           audio_data.SAMPLE_FORMAT.
                            channel: number of channels.
                            rate: sampling rate.
        @param path: The path to the file.

        @raises: AudioTestDataException if the path does not exist.

        """
        self.data_format = data_format
        if not os.path.exists(path):
            raise AudioTestDataException('Can not find path %s' % path)
        self.path = path


    def get_binary(self):
        """The binary of test data.

        @returns: The binary of test data.

        """
        with open(self.path, 'rb') as f:
            return f.read()


AUDIO_PATH = os.path.join(os.path.dirname(__file__))

"""
This test data contains frequency sweep from 20Hz to 20000Hz in two channels.
Left channel sweeps from 20Hz to 20000Hz, while right channel sweeps from
20000Hz to 20Hz. The sweep duration is 2 seconds. The begin and end of the file
is padded with 0.2 seconds of silence. The file is two-channel raw data with
each sample being a signed 16-bit integer in little-endian with sampling rate
48000 samples/sec.
"""
SWEEP_TEST_FILE = AudioTestData(
        path=os.path.join(AUDIO_PATH, 'pad_sweep_pad_16.raw'),
        data_format=dict(file_type='raw',
                         sample_format='S16_LE',
                         channel=2,
                         rate=48000))

"""
This test data contains fixed frequency sine wave in two channels.
Left channel is 2KHz, while right channel is 1KHz. The duration is 6 seconds.
The file format is two-channel raw data with each sample being a signed
16-bit integer in little-endian with sampling rate 48000 samples/sec.
"""
FREQUENCY_TEST_FILE = AudioTestData(
        path=os.path.join(AUDIO_PATH, 'fix_2k_1k_16.raw'),
        data_format=dict(file_type='raw',
                         sample_format='S16_LE',
                         channel=2,
                         rate=48000))
