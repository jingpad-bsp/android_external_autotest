# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import logging
import re
import subprocess
import utils

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.audio import audio_helper


_DEFAULT_CARD = '0'
_DEFAULT_VOLUME_LEVEL = 100
_DEFAULT_CAPTURE_GAIN = 2500

_AUDIO_NOT_FOUND = r'Audio\snot\sdetected'
_MEASURED_LATENCY = r'Measured\sLatency:\s(\d+)\suS'
_REPORTED_LATENCY = r'Reported\sLatency:\s(\d+)\suS'


class audiovideo_LoopbackLatency(test.test):
    version = 1

    def initialize(self,
                   card=_DEFAULT_CARD,
                   default_volume_level=_DEFAULT_VOLUME_LEVEL,
                   default_capture_gain=_DEFAULT_CAPTURE_GAIN):
        '''Setup the deps for the test.

        Args:
            card: The index of the sound card to use.
            default_volume_level: The default volume level.
            defalut_capture_gain: The default capture gain.

        Raises: error.TestError if the deps can't be run
        '''
        self._card = card

        self._volume_level = default_volume_level
        self._capture_gain = default_capture_gain

        self._ah = audio_helper.AudioHelper(self)
        self._ah.setup_deps(['audioloop'])

        super(audiovideo_LoopbackLatency, self).initialize()

    def run_once(self):
        self._ah.set_volume_levels(self._volume_level, self._capture_gain)
        self._loopback_latency_path = os.path.join(self.autodir, 'deps',
                'audioloop', 'src', 'loopback_latency')
        noise_threshold =  400
        measured_latency = None
        reported_latency = None
        deviation = None
        while True:
            cmdargs = [self._loopback_latency_path, '-n', str(noise_threshold)]
            proc = subprocess.Popen(cmdargs, stdout=subprocess.PIPE)
            audio_detected = True

            # Parse loopback_latency output
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                match = re.search(_MEASURED_LATENCY, line, re.I)
                if match:
                    measured_latency = int(match.group(1))
                match = re.search(_REPORTED_LATENCY, line, re.I)
                if match:
                    reported_latency = int(match.group(1))
                if re.search(_AUDIO_NOT_FOUND, line, re.I):
                    audio_detected = False

            if measured_latency and reported_latency:
                deviation = (1.0 * abs(measured_latency - reported_latency) /
                             reported_latency)
                logging.info('Tested with threshold %d.\nMeasured %d, reported '
                             '%d uS, deviation %f%%\n' %
                             (noise_threshold, measured_latency,
                              reported_latency, deviation * 100))
            if not audio_detected:
                logging.info('Audio not detected.')
                break
            noise_threshold *= 2
        if deviation is None:
            raise error.TestError('No audio detected')
        elif deviation > .02:
            raise error.TestError('Latency deviation(%f) too much, measured %d,'
                                  ' reported %d\n' %
                                  (deviation, measured_latency,
                                   reported_latency))
