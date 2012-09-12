# -*- coding: utf-8 -*-
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# DESCRIPTION :
#
# This is a factory test for the audio function. An external loopback dongle
# is required to automatically capture and detect the playback tones.

import os
import re
import subprocess
import tempfile
import time
import utils

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory_setup_modules
from cros.factory.test import factory
from cros.factory.test.test_ui import UI
from cros.factory.test.event import Event
from autotest_lib.client.cros.audio import audio_helper
from cros.factory.test import ui as ful


# Default setting
_DEFAULT_FREQ_HZ = 1000
_DEFAULT_FREQ_THRESHOLD_HZ = 50
_DEFAULT_DURATION_SEC = 1

# Pass threshold
_PASS_THRESHOLD = 50.0

# Regular expressions to match audiofuntest message.
_AUDIOFUNTEST_STOP_RE = re.compile('^Stop')
_AUDIOFUNTEST_SUCCESS_RATE_RE = re.compile('.*rate\s=\s(.*)$')

_MUTE_LEFT_MIXER_SETTINGS = [{'name': '"Headphone Playback Switch"',
                              'value': 'off,on'},
                             {'name': '"Master Playback Switch"',
                              'value': 'off,on'},
                             {'name': '"Speaker Playback Switch"',
                              'value': 'off,on'}]
_MUTE_RIGHT_MIXER_SETTINGS = [{'name': '"Headphone Playback Switch"',
                               'value': 'on,off'},
                              {'name': '"Master Playback Switch"',
                               'value': 'on,off'},
                              {'name': '"Speaker Playback Switch"',
                               'value': 'on,off'}]

class factory_AudioLoop(test.test):
    version = 1

    def start_run_test(self, event):
        if self._audiofuntest:
            for odev in self._output_devices:
                for settings in [_MUTE_LEFT_MIXER_SETTINGS,
                        _MUTE_RIGHT_MIXER_SETTINGS]:
                    for idev in self._input_devices:
                        self._ah.set_mixer_controls(settings)
                        self.run_audiofuntest(idev, odev)
                        time.sleep(0.5)

            self.ui.Pass()
        else:
            self.audio_loopback()
        return True

    def run_audiofuntest(self, idev, odev):
        '''
        Sample audiofuntest message:

        O: carrier = 41, delay = 6, success = 60, fail = 0, rate = 100.0
        Stop play tone
        Stop capturing data
        '''
        factory.console.info('Run audiofuntest')
        self._proc = subprocess.Popen([self._audiofuntest_path, '-r', '48000',
                '-i', idev, '-o', odev], stderr=subprocess.PIPE)

        while True:
            proc_output = self._proc.stderr.readline()
            if not proc_output:
                break

            m = _AUDIOFUNTEST_SUCCESS_RATE_RE.match(proc_output)
            if m is not None:
                self._last_success_rate = float(m.group(1))
                self.ui.CallJSFunction('testInProgress',
                                       self._last_success_rate)

            m = _AUDIOFUNTEST_STOP_RE.match(proc_output)
            if m is not None:
                 if (hasattr(self, '_last_success_rate') and
                         self._last_success_rate is not None):
                     self._result = self._last_success_rate > _PASS_THRESHOLD
                     break

        # Show instant message and wait for a while
        if hasattr(self, '_result') and self._result:
            return True
        elif hasattr(self, '_last_success_rate'):
            self.ui.CallJSFunction('testFailResult', self._last_success_rate)
            time.sleep(1)
            self.ui.Fail('Test Fail. The success rate is %.1f, too low!' %
                         self._last_success_rate)
        else:
            self.ui.Fail('audiofuntest terminated unexpectedly')
        return True

    def audio_loopback(self):
        for input_device in self._input_devices:
            self._ah = audio_helper.AudioHelper(self,
                    input_device=input_device,
                    record_duration=self._duration)
            # TODO(hychao): split deps and I/O devices to different
            # utils so we can setup deps only once.
            self._ah.setup_deps(['sox'])
            for output_device in self._output_devices:
                # Record a sample of "silence" to use as a noise profile.
                with tempfile.NamedTemporaryFile(mode='w+t') as noise_file:
                    factory.console.info('Noise file: %s' % noise_file.name)
                    self._ah.record_sample(noise_file.name)

                    # Playback sine tone and check the recorded audio frequency.
                    self._ah.loopback_test_channels(noise_file,
                            lambda ch: self.playback_sine(ch, output_device),
                            self.check_recorded_audio)

        if self._result is True:
            self.ui.CallJSFunction('testPassResult')
            time.sleep(0.5)
            self.ui.Pass()

    def playback_sine(self, unused_channel, output_device='default'):
        cmd = '%s -n -t alsa %s synth %d sine %d' % (self._ah.sox_path,
                output_device, self._duration, self._freq)
        utils.system(cmd)

    def check_recorded_audio(self, sox_output):
        freq = self._ah.get_rough_freq(sox_output)
        if abs(freq - self._freq) > _DEFAULT_FREQ_THRESHOLD_HZ:
            self.ui.Fail('Test Fail at frequency %d' % freq)
        else:
            self._result = True
            factory.console.info('Got frequency %d' % freq)

    def run_once(self, audiofuntest=True, duration=_DEFAULT_DURATION_SEC,
            input_devices=['hw:0,0'], output_devices=['hw:0,0'],
            mixer_controls=None):
        factory.console.info('%s run_once' % self.__class__)

        self._audiofuntest = audiofuntest
        self._duration = duration
        self._freq = _DEFAULT_FREQ_HZ
        self._input_devices = input_devices
        self._output_devices = output_devices

        # Create a default audio helper to do the setup jobs.
        self._ah = audio_helper.AudioHelper(self, record_duration=duration)
        if mixer_controls is not None:
            self._ah.set_mixer_controls(mixer_controls)

        # Setup dependencies
        self._ah.setup_deps(['sox', 'test_tones'])
        self._audiofuntest_path = os.path.join(self.autodir, 'deps',
                'test_tones', 'src', 'audiofuntest')
        if not (os.path.exists(self._audiofuntest_path) and
                os.access(self._audiofuntest_path, os.X_OK)):
            raise error.TestError(
                    '%s is not an executable' % self._audiofuntest_path)

        # Setup HTML UI, and event handler
        self.ui = UI()
        self.ui.AddEventHandler('start_run_test', self.start_run_test)

        factory.console.info('Run UI')
        self.ui.Run()

