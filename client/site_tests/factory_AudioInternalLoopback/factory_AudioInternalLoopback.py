# -*- coding: utf-8 -*-
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This is a factory test to test the audio.  Operator will test both record and
# playback for headset and built-in audio.  Recordings are played back for
# confirmation.  An additional pre-recorded sample is played to confirm speakers
# operate independently


import gtk
import logging
import os
import pango
import re
import sys
import subprocess

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.cros import factory_setup_modules
from autotest_lib.client.cros.audio import audio_helper
from cros.factory.test import factory
from cros.factory.test import ui as ful
from gtk import gdk


_MESSAGE_STR = ('Audio is now looping back.\n' +
                'Press Return if test passed.\n' +
                'Press Tab if it failed.\n')

class factory_AudioInternalLoopback(test.test):
    version = 1

    def start_audioloop(self, indev, outdev):
        cmdargs = [audio_helper.AUDIOLOOP_PATH, '-i', indev, '-o', outdev]
        self._process = subprocess.Popen(cmdargs)

    def stop_audioloop(self):
        self._process.kill()

    def key_release_callback(self, widget, event):
        if event.keyval == gtk.keysyms.Return:
            gtk.main_quit()
        if event.keyval == gtk.keysyms.Tab:
            raise error.TestFail('Test Failed')
        return True

    def register_callbacks(self, window):
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gdk.KEY_RELEASE_MASK)

    def run_once(self, indev='hw:0,0', outdev='hw:0,0'):

        factory.log('%s run_once' % self.__class__)

        label = ful.make_label(_MESSAGE_STR)

        self.start_audioloop(indev, outdev)

        test_widget = gtk.EventBox()
        test_widget.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        test_widget.add(label)

        ful.run_test_widget(self.job, test_widget,
            window_registration_callback=self.register_callbacks)

        self.stop_audioloop()

        factory.log('%s run_once finished' % repr(self.__class__))
