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

_LATENCY_DIFF_LIMIT_US = 3000
_NOISE_THRESHOLD = 1600

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
        success = False

        result = self._ah.loopback_latency_check(n=_NOISE_THRESHOLD)
        if result:
            diff = abs(result[0] - result[1])
            logging.info('Tested latency with threshold %d.\nMeasured %d,'
                         'reported %d uS, diff %d us\n' %
                         (_NOISE_THRESHOLD, result[0], result[1], diff))

            # Difference between measured and reported latency should
            # within 3 ms.
            if diff < _LATENCY_DIFF_LIMIT_US:
                success = True
        else:
            raise error.TestError('Audio not detected at threshold %d' %
                                  _NOISE_THRESHOLD)

        if not success:
            raise error.TestError('Latency difference too much, diff limit'
                                  '%d us' % _LATENCY_DIFF_LIMIT_US)
