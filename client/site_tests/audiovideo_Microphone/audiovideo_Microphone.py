# Copyright (c) 2010 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import tempfile

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.audio import alsa_utils

DURATION = 3
TOLERANT_RATIO = 0.1

class audiovideo_Microphone(test.test):
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
        sndcard_id = alsa_utils.get_default_soundcard_id()

        # Microphone should be on by default.
        if utils.get_cpu_arch() != "arm":
            cmd = 'amixer -D hw:%d cget name="Capture Switch"'
            output = utils.system_output(cmd % sndcard_id)
            if 'values=on,on' not in output:
                raise error.TestFail('The microphone is not on by default.')
        else:
            # TODO(jiesun): find consistent way to find the ALSA mixer control
            # names for both internal mic and external mic on ARM, which is
            # independent of the audio codec hardware vendor.
            logging.warning("Can not verify the microphone capture switch.")

        # Mono and stereo capturing should work fine @ 44.1KHz and 48KHz.
        self.verify_capture(1, 44100)
        self.verify_capture(1, 48000)
        self.verify_capture(2, 48000)
        self.verify_capture(2, 44100)

        # TODO(zhurunz):
        # Low latency capturing should work fine with low CPU usage.
