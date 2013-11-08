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

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory_setup_modules
from cros.factory.test import factory
from cros.factory.test.test_ui import UI
from autotest_lib.client.cros.audio import audio_helper


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
_UNMUTE_MIXER_SETTINGS = [{'name': '"Headphone Playback Switch"',
                           'value': 'on,on'},
                          {'name': '"Master Playback Switch"',
                           'value': 'on,on'},
                          {'name': '"Speaker Playback Switch"',
                           'value': 'on,on'}]


class factory_AudioLoop(test.test):
    version = 1

    def start_run_test(self, event):
        if self._audiofuntest:
            for odev in self._output_devices:
                for settings in [self._mute_left_mixer_settings,
                                 self._mute_right_mixer_settings]:
                    for idev in self._input_devices:
                        # Skip blacklisted test combination.
                        channel = 'left'
                        if settings == self._mute_left_mixer_settings:
                            channel = 'right'
                        if self.in_blacklist_combinations(channel, idev):
                            continue

                        audio_helper.set_mixer_controls(settings, self._card)
                        if self._mute_device_mixer_settings:
                            audio_helper.set_mixer_controls(
                                    self._mute_device_mixer_settings,
                                    self._card)
                        self.run_audiofuntest(idev, odev,
                                              self._audiofuntest_duration)
                        time.sleep(0.5)
            self.ui.Pass()
        else:
            self.audio_loopback()
        return True

    def in_blacklist_combinations(self, channel, idev):
        return (channel, idev) in self._blacklist_combinations

    def run_audiofuntest(self, idev, odev, dur):
        '''
        Sample audiofuntest message:

        O: carrier = 41, delay = 6, success = 60, fail = 0, rate = 100.0
        Stop play tone
        Stop capturing data
        '''
        factory.console.info('Run audiofuntest')
        self._proc = subprocess.Popen([audio_helper.AUDIOFUNTEST_PATH,
                                       '-r', '48000',
                                       '-i', idev, '-o', odev, '-l',
                                       '%d' % dur], stderr=subprocess.PIPE)

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
                     self._test_result = (
                         self._last_success_rate > _PASS_THRESHOLD)
                     break

        # Unmute channels
        audio_helper.set_mixer_controls(self._unmute_mixer_settings, self._card)

        # Show instant message and wait for a while
        if self._test_result:
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

            def record_callback(filename):
                rec_cmd = 'arecord -D %s -f dat -d %f' % (input_device,
                                                          self._duration)
                audio_helper.record_sample(filename, rec_cmd)

            # TODO(hychao): split deps and I/O devices to different
            # utils so we can setup deps only once.
            for output_device in self._output_devices:
                # Record a sample of "silence" to use as a noise profile.
                with tempfile.NamedTemporaryFile(mode='w+t') as noise_file:
                    factory.console.info('Noise file: %s' % noise_file.name)
                    audio_helper.record_sample(noise_file.name, rec_cmd)

                    # Playback sine tone and check the recorded audio frequency.
                    audio_helper.loopback_test_channels(noise_file.name,
                            self.resultsdir,
                            lambda ch: audio_helper.play_sine(ch, output_device,
                                                              self._freq,
                                                              self._duration),
                            self.check_recorded_audio,
                            record_callback=record_callback)

        if self._test_result:
            self.ui.CallJSFunction('testPassResult')
            time.sleep(0.5)
            self.ui.Pass()

    def check_recorded_audio(self, sox_output):
        freq = audio_helper.get_rough_freq(sox_output)
        if abs(freq - self._freq) > _DEFAULT_FREQ_THRESHOLD_HZ:
            self._test_result = False
            self.ui.Fail('Test Fail at frequency %d' % freq)
        else:
            self._test_result = True
            factory.console.info('Got frequency %d' % freq)

    def get_card_index(self, devs):
        '''
        Gets the card index from given device names. If more then
        one card is covered, return the first found one.
        Args:
            devs - List of alsa device names
        '''
        dev_name_pattern = re.compile(".*?hw:([0-9]+),([0-9]+)")
        for dev in devs:
            match = dev_name_pattern.match(dev)
            if match:
                return match.group(1)
        return '0'

    def run_once(self, audiofuntest=True, audiofuntest_duration=10,
            blacklist_combinations=[],
            duration=_DEFAULT_DURATION_SEC,
            input_devices=['hw:0,0'], output_devices=['hw:0,0'],
            mixer_controls=None, device_to_mute=None,
            mute_left_mixer_settings=_MUTE_LEFT_MIXER_SETTINGS,
            mute_right_mixer_settings=_MUTE_RIGHT_MIXER_SETTINGS,
            unmute_mixer_settings=_UNMUTE_MIXER_SETTINGS,
            mute_device_mixer_settings=None,
            autostart=False,
            require_dongle=False):
        factory.console.info('%s run_once' % self.__class__)

        self._audiofuntest = audiofuntest
        self._audiofuntest_duration = audiofuntest_duration
        self._blacklist_combinations = blacklist_combinations
        self._duration = duration
        self._freq = _DEFAULT_FREQ_HZ
        self._input_devices = input_devices
        self._output_devices = output_devices
        self._device_to_mute = device_to_mute
        self._mute_left_mixer_settings = mute_left_mixer_settings
        self._mute_right_mixer_settings = mute_right_mixer_settings
        self._unmute_mixer_settings = unmute_mixer_settings
        self._mute_device_mixer_settings = mute_device_mixer_settings

        # Used in run_audiofuntest() and audio_loop() for test result.
        self._test_result = False

        # Guess the card index from given I/O device names.
        self._card = self.get_card_index(output_devices + input_devices)
        if mixer_controls is not None:
            audio_helper.set_mixer_controls(mixer_controls, self._card)

        # Setup HTML UI, and event handler
        self.ui = UI()
        self.ui.AddEventHandler('start_run_test', self.start_run_test)

        # If autostart, JS triggers start_run_test event.
        # Otherwise, it binds start_run_test with 's' key pressed.
        self.ui.CallJSFunction('init', autostart, require_dongle)
        factory.console.info('Run UI')
        self.ui.Run()
