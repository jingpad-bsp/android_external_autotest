#!/usr/bin/env python
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides audio test data."""

import os


class AudioTestDataException(Exception):
    """Exception for audio test data."""
    pass


class AudioTestData(object):
    """Class to represent audio test data."""
    path_on_dut = None
    path_on_server = None
    data_format = None
    def __init__(self, data_format, path_on_dut=None, path_on_server=None):
        """
        Initializes an audio test file. At least one of path_on_dut and
        path_on_server must be specified.

        @param data_format: A dict containing data format including
                            file_type, sample_format, channel, and rate.
                            file_type: file type e.g. 'raw' or 'wav'.
                            sample_format: One of the keys in
                                           audio_data.SAMPLE_FORMAT.
                            channel: number of channels.
                            rate: sampling rate.
        @param path_on_dut: The path to the file on DUT.
        @param path_on_server: The path to the file on server.

        @raise AudioTestDataException if path_on_dut and path_on_server are not
          specified.
        """
        if not path_on_dut and not path_on_server:
            raise AudioTestDataException('No path is specified.')
        self.path_on_dut = path_on_dut
        self.path_on_server = path_on_server
        self.data_format = data_format


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
        path_on_dut='/usr/local/autotest/cros/audio/pad_sweep_pad_16.raw',
        path_on_server=os.path.join(AUDIO_PATH, 'pad_sweep_pad_16.raw'),
        data_format=dict(file_type='raw',
                         sample_format='S16_LE',
                         channel=2,
                         rate=48000))
