# Copyright (c) 2010 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import tempfile

from autotest_lib.client.bin import site_utils, test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.audio import alsa_utils

DURATION = 3
TOLERANT_RATIO = 0.1
NO_MIC_DEV_LIST = ['monroe', 'panther']

class audio_Microphone(test.test):
    version = 1


    def check_recorded_filesize(
            self, filesize, duration, channels, bits, rate):
        expected = duration * channels * (bits / 8) * rate
        if abs(float(filesize) / expected - 1) > TOLERANT_RATIO:
            raise error.TestFail('File size not correct: %d' % filesize)


    def verify_capture(self, channels, rate, bits=16):
        recorded_file = tempfile.NamedTemporaryFile()
        alsa_utils.record(
                recorded_file.name, duration=DURATION, channels=channels,
                bits=bits, rate=rate)
        self.check_recorded_filesize(
                os.path.getsize(recorded_file.name),
                DURATION, channels, bits, rate)


    def run_once(self):
        if site_utils.get_board() in NO_MIC_DEV_LIST:
            raise error.TestNAError("This test can't run on this host.")
        # Mono and stereo capturing should work fine @ 44.1KHz and 48KHz.
        self.verify_capture(1, 44100)
        self.verify_capture(1, 48000)
        self.verify_capture(2, 48000)
        self.verify_capture(2, 44100)
