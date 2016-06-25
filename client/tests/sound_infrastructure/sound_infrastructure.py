# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re
import stat
import subprocess

from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils

_SND_DEV_DIR = '/dev/snd/'

class sound_infrastructure(test.test):
    """
    Tests that the expected sound infrastructure is present.

    Check that at least one playback and capture device exists and that their
    permissions are configured properly.

    """
    version = 2
    _NO_RECORDER_BOARDS_LIST = ['veyron_mickey', 'veyron_rialto']

    def check_snd_dev_perms(self, filename):
        desired_mode = (stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP |
                        stat.S_IWGRP | stat.S_IFCHR)
        st = os.stat(filename)
        if (st.st_mode != desired_mode):
            raise error.TestError("Incorrect permissions for %s" % filename)

    def check_sound_files(self, playback=True, record=True):
        """Checks sound files present in snd directory.

        @param playback: Checks playback device.
        @param record: Checks record device.

        @raises: error.TestError if sound file is missing.

        """
        patterns = {'^controlC(\d+)': False}
        if playback:
            patterns['^pcmC(\d+)D(\d+)p$'] = False
        if record:
            patterns['^pcmC(\d+)D(\d+)c$'] = False

        filenames = os.listdir(_SND_DEV_DIR)

        for filename in filenames:
            for pattern in patterns:
                if re.match(pattern, filename):
                    patterns[pattern] = True
                    self.check_snd_dev_perms(_SND_DEV_DIR + filename)

        for pattern in patterns:
            if not patterns[pattern]:
                raise error.TestError("Missing device %s" % pattern)

    def check_device_list(self, playback=True, record=True):
        """Checks sound card and device list by alsa utils command.

        @param playback: Checks playback sound card and devices.
        @param record: Checks record sound card and devices.

        @raises: error.TestError if no playback/record devices found.

        """
        no_cards_pattern = '.*no soundcards found.*'
        if playback:
            aplay = subprocess.Popen(["aplay", "-l"], stderr=subprocess.PIPE)
            aplay_list = aplay.communicate()[1]
            if aplay.returncode or re.match(no_cards_pattern, aplay_list):
                raise error.TestError("No playback devices found by aplay")

        if record:
            no_cards_pattern = '.*no soundcards found.*'
            arecord = subprocess.Popen(
                    ["arecord", "-l"], stderr=subprocess.PIPE)
            arecord_list = arecord.communicate()[1]
            if arecord.returncode or re.match(no_cards_pattern, arecord_list):
                raise error.TestError("No record devices found by arecord")

    def run_once(self):
        record = utils.get_board().lower() not in self._NO_RECORDER_BOARDS_LIST
        self.check_sound_files(True, record)
        self.check_device_list(True, record)
