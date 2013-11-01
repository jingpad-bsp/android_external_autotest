# Copyright (c) 2010 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, tempfile, time, utils

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.audio import audio_helper

DURATION = 30
BYTES_PER_SAMPLE = 2
TOLERATE = 0.8

class audiovideo_Microphone(test.test):
    version = 1

    def verify_capture(self, sndcard, ch, rate):
        cmd = "arecord -D plughw:%s -f dat -c %s -r %s -d %d %s"
        recorded_file = tempfile.NamedTemporaryFile(mode='w+t').name
        try:
            utils.system(cmd % (sndcard, ch, rate, DURATION, recorded_file))
            size = os.path.getsize(recorded_file)
            if (size < DURATION * rate * ch * BYTES_PER_SAMPLE * TOLERATE) :
                raise error.TestFail("File size not correct: %d" % size)
        finally:
            os.remove(recorded_file)


    def run_once(self):
        cpuType = utils.get_cpu_arch()

        sndcard = audio_helper.find_hw_soundcard_name(cpuType)
        if sndcard is None:
            raise error.TestError('No sound card detected')

        # Microphone should be on by default.
        if cpuType != "arm":
            cmd = 'amixer -D hw:%s cget name="Capture Switch" | grep values=on,on'
            output = utils.system_output(cmd % sndcard)
            if (output == ''):
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
