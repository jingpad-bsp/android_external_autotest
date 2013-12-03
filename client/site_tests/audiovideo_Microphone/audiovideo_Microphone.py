# Copyright (c) 2010 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, tempfile, time, utils

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.audio import audio_helper

DURATION = 3
BYTES_PER_SAMPLE = 2
TOLERANT_RATIO = 0.1

class audiovideo_Microphone(test.test):
    version = 1


    def check_recorded_filesize(self, filesize, duration, channels, rate):
        expected = duration * channels * BYTES_PER_SAMPLE * rate
        if abs(float(filesize) / expected - 1) > TOLERANT_RATIO:
            raise error.TestFail('File size not correct: %d' % filesize)


    def verify_capture(self, sndcard, channels, rate):
        with tempfile.NamedTemporaryFile() as recorded_file:
            cmd = "arecord -D plughw:%s -f dat -c %s -r %s -d %d %s"
            utils.system(cmd % (sndcard, channels, rate,
                                DURATION, recorded_file.name))
            self.check_recorded_filesize(
                    os.path.getsize(recorded_file.name),
                    DURATION, channels, rate)


    def run_once(self):
        sndcard = audio_helper.find_hw_soundcard_name()
        if sndcard is None:
            raise error.TestError('No sound card detected')

        # Microphone should be on by default.
        if utils.get_cpu_arch() != "arm":
            cmd = 'amixer -D hw:%s cget name="Capture Switch"'
            output = utils.system_output(cmd % sndcard)
            if 'values=on,on' not in output:
                raise error.TestFail('The microphone is not on by default.')
        else:
            # TODO(jiesun): find consistent way to find the ALSA mixer control
            # names for both internal mic and external mic on ARM, which is
            # independent of the audio codec hardware vendor.
            logging.warning("Can not verify the microphone capture switch.")

        # Mono and stereo capturing should work fine @ 44.1KHz and 48KHz.
        self.verify_capture(sndcard, 1, 44100)
        self.verify_capture(sndcard, 1, 48000)
        self.verify_capture(sndcard, 2, 48000)
        self.verify_capture(sndcard, 2, 44100)

        # TODO(zhurunz):
        # Low latency capturing should work fine with low CPU usage.
