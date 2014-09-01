#!/usr/bin/env python
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides abstraction of audio data."""

import contextlib
import struct
import StringIO


"""The dict containing information on how to parse sample from raw data.

Keys: The sample format as in aplay command.
Values: A dict containing:
    message: Human-readable sample format.
    struct_format: Format used in struct.unpack.
    size_bytes: Number of bytes for one sample.
"""
SAMPLE_FORMATS = dict(
        S32_LE=dict(
                message='Signed 32-bit integer, little-endian',
                struct_format='<i',
                size_bytes=4),
        S16_LE=dict(
                message='Signed 16-bit integer, little-endian',
                struct_format='<h',
                size_bytes=2))


class AudioRawData(object):
    """The abstraction of audio raw data.

    @property channel: The number of channels.
    @property channel_data: A list of lists containing samples in each channel.
                            E.g., The third sample in the second channel is
                            channel_data[1][2].
    @property sample_format: The sample format which should be one of the keys
                             in audio_data.SAMPLE_FORMATS.
    """
    def __init__(self, binary, channel, sample_format):
        """Initializes an AudioRawData.

        @param binary: A string containing binary data.
        @param channel: The number of channels.
        @param sample_format: One of the keys in audio_data.SAMPLE_FORMATS.
        """
        self.channel = channel
        self.channel_data = [[] for _ in xrange(self.channel)]
        self.sample_format = sample_format
        self.read_binary(binary)


    def read_one_sample(self, handle):
        """Reads one sample from handle.

        @param handle: A handle that supports read() method.

        @return: A number read from file handle based on sample format.
                 None if there is no data to read.
        """
        data = handle.read(SAMPLE_FORMATS[self.sample_format]['size_bytes'])
        if data == '':
            return None
        number, = struct.unpack(
                SAMPLE_FORMATS[self.sample_format]['struct_format'], data)
        return number


    def read_binary(self, binary):
        """Reads samples from binary and fills channel_data.

        Reads one sample for each channel and repeats until the end of
        input binary.

        @param binary: A string containing binary data.
        """
        channel_index = 0
        with contextlib.closing(StringIO.StringIO(binary)) as f:
            number = self.read_one_sample(f)
            while number is not None:
                self.channel_data[channel_index].append(number)
                channel_index = (channel_index + 1) % self.channel
                number = self.read_one_sample(f)
