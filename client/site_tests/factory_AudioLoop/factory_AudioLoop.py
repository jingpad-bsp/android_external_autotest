# -*- coding: utf-8 -*-
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# DESCRIPTION :
#
# This is a factory test for the audio function. An external loopback dongle
# is required to automatically capture and detect the playback tones.

import glib
import gtk
import os
import re
import subprocess
import tempfile
import utils

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.audio import audio_helper
from autotest_lib.client.cros.factory import ui as ful

_DEFAULT_FREQ_HZ = 1000
_DEFAULT_FREQ_THRESHOLD_HZ = 50
_DEFAULT_DURATION_SEC = 1

_LABEL_START_STR = 'Hit s to start loopback test\n' +\
        '按s鍵開始音源回放測試\n\n'
_LABEL_IN_PROGRESS_STR = 'Loopback testing...\n' +\
        '音源回放測試中...\n\n'
_LABEL_SUCCESS_RATE = 'Success rate %f\n'

# Regular expressions to match audiofuntest message.
_AUDIOFUNTEST_STOP_RE = re.compile('^Stop')
_AUDIOFUNTEST_SUCCESS_RATE_RE = re.compile('.*rate\s=\s(.*)$')

class factory_AudioLoop(test.test):
    version = 1

    def key_press_callback(self, widget, event):
        if event.keyval == ord('s'):
            self._status_box.remove(self._status_label)
            self._status_label = None
            self._status_label = ful.make_label(_LABEL_IN_PROGRESS_STR,
                                                fg = ful.WHITE)
            self._status_box.add(self._status_label)
        if self._audiofuntest:
            self._success_rate_box.remove(self._success_rate_label)
            self._success_rate_label = None
            self._success_rate_label = ful.make_label("", fg = ful.WHITE)
            self._success_rate_box.add(self._success_rate_label)

        self._main_widget.show_all()
        self._main_widget.queue_draw()
        return True

    def key_release_callback(self, widget, event):
        if event.keyval == ord('s'):
            if self._audiofuntest:
                self._proc = subprocess.Popen(self._audiofuntest_path,
                        stderr=subprocess.PIPE)
                self._gio_tag = glib.io_add_watch(self._proc.stderr, glib.IO_IN,
                        self.audiofuntest_cb, priority=glib.PRIORITY_LOW)
            else:
                self.audio_loopback()
                gtk.main_quit()

        return True

    def audio_loopback(self):
        # Record a sample of "silence" to use as a noise profile.
        with tempfile.NamedTemporaryFile(mode='w+t') as noise_file:
            factory.log('Noise file: %s' % noise_file.name)
            self._ah.record_sample(noise_file.name)

            # Playback sine tone and check the recorded audio frequency.
            self._ah.loopback_test_channels(noise_file,
                    self.playback_sine,
                    self.check_recorded_audio)

    def playback_sine(self, unused_channel):
        cmd = '%s -n -d synth %d sine %d' % (self._ah.sox_path, self._duration,
                self._freq)
        utils.system(cmd)

    def check_recorded_audio(self, sox_output):
        freq = self._ah.get_rough_freq(sox_output)
        if abs(freq - self._freq) > _DEFAULT_FREQ_THRESHOLD_HZ:
            raise error.TestError('Frequency %d not match' % freq)
        self._result = True
        factory.log('Got frequency %d' % freq)

    def audiofuntest_cb(self, source, cb_condition):
        '''
        Sample audiofuntest message:

        O: carrier = 41, delay =  6, success =  60, fail =   0, rate = 100.0
        Stop play tone
        Stop capturing data
        '''
        line = source.readline()

        m = _AUDIOFUNTEST_SUCCESS_RATE_RE.match(line)
        if m is not None:
            self._last_success_rate = float(m.group(1))

            self._success_rate_box.remove(self._success_rate_label)
            self._success_rate_label = None
            self._success_rate_label = ful.make_label(_LABEL_SUCCESS_RATE %
                    self._last_success_rate, fg = ful.WHITE)
            self._success_rate_box.add(self._success_rate_label)
            self._main_widget.show_all()
            self._main_widget.queue_draw()

        m = _AUDIOFUNTEST_STOP_RE.match(line)
        if m is not None:
            glib.source_remove(self._gio_tag)
            if (hasattr(self, '_last_success_rate') and
                    self._last_success_rate is not None):
                self._result = self._last_success_rate > 50.0
                gtk.main_quit()

        return True

    def register_callbacks(self, window):
        window.connect('key-press-event', self.key_press_callback)
        window.add_events(gtk.gdk.KEY_PRESS_MASK)
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gtk.gdk.KEY_RELEASE_MASK)

    def run_once(self, audiofuntest=False, duration=_DEFAULT_DURATION_SEC,
            input='default', mixer_controls=None):
        factory.log('%s run_once' % self.__class__)

        self._audiofuntest = audiofuntest
        self._duration = duration
        self._freq = _DEFAULT_FREQ_HZ

        self._ah = audio_helper.AudioHelper(self, record_duration=duration,
                input_device=input)
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

        # Status box and label
        self._status_box = gtk.EventBox()
        self._status_box.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        self._status_label = ful.make_label(_LABEL_START_STR,
                                            fg = ful.WHITE)
        self._status_box.add(self._status_label)

        # Success rate box and label
        self._success_rate_box = gtk.EventBox()
        self._success_rate_box.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        self._success_rate_label = ful.make_label("", fg = ful.WHITE)
        self._success_rate_box.add(self._success_rate_label)

        self._label_list = gtk.VBox()
        self._label_list.pack_start(self._status_box, False, False)
        self._label_list.pack_end(self._success_rate_box, False, False)
        self._main_widget = gtk.EventBox()
        self._main_widget.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        self._main_widget.add(self._label_list)

        ful.run_test_widget(self.job, self._main_widget,
                window_registration_callback = self.register_callbacks)

        if not self._result:
            raise error.TestFail('ERROR: loopback test fail')
