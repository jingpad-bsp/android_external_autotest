# Copyright (c) 2010 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, time, utils

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

DURATION = 30
BYTES_PER_SAMPLE = 2
TOLERATE = 0.8

class audiovideo_Microphone(test.test):
    version = 1

    def verify_capture(self, ch, rate):
        file_name = "/tmp/%s-%s.capture" % (ch, rate)
        cmd = "rm -f %s" % file_name
        utils.system(cmd, ignore_status=True)
        cmd = "arecord -f dat -D default -c %s -r %s -d %d %s"
        cmd = cmd % (ch, rate, DURATION, file_name)
        utils.system(cmd)
        size = os.path.getsize(file_name)
        if (size < DURATION * rate * ch * BYTES_PER_SAMPLE * TOLERATE) :
            raise error.TestFail("File size not correct: %s" % file_name)
        utils.system("rm -f %s" % file_name)


    def run_once(self):
        cpuType = utils.get_cpu_arch()
        # Microphone should be on by default.
        if cpuType != "arm":
            cmd = 'amixer -c 0 cget name="Capture Switch" | grep values=on,on'
            output = utils.system_output(cmd)
            if (output == ''):
                raise error.TestFail('The microphone is not on by default.')
        else:
            # TODO(jiesun): find consistent way to find the ALSA mixer control
            # names for both internal mic and external mic on ARM, which is
            # independent of the audio codec hardware vendor.
            print "Warning: Can not verify the microphone capture switch."

        # Mono and stereo capturing should work fine @ 44.1KHz and 48KHz.
        self.verify_capture(1, 44100)
        self.verify_capture(1, 48000)
        self.verify_capture(2, 48000)
        self.verify_capture(2, 44100)

        # TODO(zhurunz):
        # Low latency capturing should work fine with low CPU usage.
