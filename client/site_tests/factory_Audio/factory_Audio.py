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
import re
import sys

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils


_LABEL_BIG_SIZE = (280, 60)
_LABEL_STATUS_SIZE = (140, 30)
_LABEL_START_STR = 'hit SPACE to start each audio test\n' +\
    '按空白鍵開始各項聲音測試\n\n'
_LABEL_RESPONSE_STR = ful.USER_PASS_FAIL_SELECT_STR + '\n'
_SAMPLE_LIST = ['Headset Audio Test', 'Built-in Audio Test']
_VERBOSE = False


class factory_Audio(test.test):
    version = 1

    def audio_subtest_widget(self, name):
        vb = gtk.VBox()
        ebh = gtk.EventBox()
        ebh.modify_bg(gtk.STATE_NORMAL, ful.LABEL_COLORS[ful.ACTIVE])
        ebh.add(ful.make_label(name, size=_LABEL_BIG_SIZE,
                               fg=ful.BLACK))
        vb.pack_start(ebh)
        vb.pack_start(ful.make_vsep(3), False, False)
        if re.search('Headset', name):
            lab_str = 'Connect headset to device\n將耳機接上音源孔'
        else:
            lab_str = 'Remove headset from device\n將耳機移開音源孔'
        vb.pack_start(ful.make_label(lab_str, fg=ful.WHITE))
        vb.pack_start(ful.make_vsep(3), False, False)
        vb.pack_start(ful.make_label(\
                'Press & hold \'r\' to record\n壓住 \'r\' 鍵開始錄音\n' + \
                    '[Playback will follow]\n[之後會重播錄到的聲音]\n\n' + \
                    'Press & hold \'p\' to play sample\n' + \
                    '壓住 \'p\' 鍵以播放範例'))
        vb.pack_start(ful.make_vsep(3), False, False)
        vb.pack_start(ful.make_label(ful.USER_PASS_FAIL_SELECT_STR,
                                     fg=ful.WHITE))

        # Need event box to effect bg color.
        eb = gtk.EventBox()
        eb.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        eb.add(vb)

        self._subtest_widget = eb

        self._test_widget.remove(self._top_level_test_list)
        self._test_widget.add(self._subtest_widget)
        self._test_widget.show_all()

    def close_bgjob(self, sample_name):
        job = self._bg_job
        if job:
            utils.nuke_subprocess(job.sp)
            utils.join_bg_jobs([job], timeout=1)
            result = job.result
            if _VERBOSE and (result.stdout or result.stderr):
                raise error.CmdError(
                    sample_name, result,
                    'stdout: %s\nstderr: %s' % (result.stdout, result.stderr))
        self._bg_job = None

    def goto_next_sample(self):
        if not self._sample_queue:
            gtk.main_quit()
            return
        self._current_sample = self._sample_queue.pop()
        name = self._current_sample
        self._status_map[name] = ful.ACTIVE

    def cleanup_sample(self):
        factory.log('Inside cleanup_sample')
        self._test_widget.remove(self._subtest_widget)
        self._subtest_widget = None
        self._test_widget.add(self._top_level_test_list)
        self._test_widget.show_all()
        self.goto_next_sample()

    def key_press_callback(self, widget, event):
        name = self._current_sample
        if (event.keyval == gtk.keysyms.space and self._subtest_widget is None):
            # Start subtest.
            self.audio_subtest_widget(name)
        # Make sure we are not already recording. We can get repeated events.
        elif self._active == False:
            self.close_bgjob(name)
            cmd = None
            if event.keyval == ord('r'):
                # Record via mic.
                if os.path.isfile('rec.wav'):
                    os.unlink('rec.wav')
                cmd = 'arecord -f dat -t wav rec.wav'
            elif event.keyval == ord('p'):
                # Playback canned audio.
                cmd = 'aplay %s' % self._audio_sample_path
            if cmd:
                self._active = True
                self._bg_job = utils.BgJob(cmd, stderr_level=logging.DEBUG)
                factory.log("cmd: " + cmd)
        self._test_widget.queue_draw()
        return True

    def key_release_callback(self, widget, event):
        name = self._current_sample
        if event.keyval == gtk.keysyms.Tab:
            self._status_map[name] = ful.FAILED
            self.cleanup_sample()
        elif event.keyval == gtk.keysyms.Return:
            self._status_map[name] = ful.PASSED
            self.cleanup_sample()
        elif event.keyval == ord('Q'):
            gtk.main_quit()
        elif event.keyval == ord('r'):
            self.close_bgjob(name)
            cmd = 'aplay rec.wav'
            self._bg_job = utils.BgJob(cmd, stderr_level=logging.DEBUG)
            factory.log("cmd: " + cmd)
            # Clear active recording state.
            self._active = False
        elif event.keyval == ord('p'):
            self.close_bgjob(name)
            # Clear active playing state.
            self._active = False
        self._test_widget.queue_draw()
        return True

    def label_status_expose(self, widget, event, name=None):
        status = self._status_map[name]
        widget.set_text(status)
        widget.modify_fg(gtk.STATE_NORMAL, ful.LABEL_COLORS[status])

    def make_sample_label_box(self, name):
        eb = gtk.EventBox()
        eb.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        label_status = ful.make_label(ful.UNTESTED, size=_LABEL_STATUS_SIZE,
                                      alignment=(0, 0.5),
                                      fg=ful.LABEL_COLORS['UNTESTED'])
        expose_cb = lambda *x: self.label_status_expose(*x, **{'name':name})
        label_status.connect('expose_event', expose_cb)
        label_en = ful.make_label(name, alignment=(1,0.5))
        label_sep = ful.make_label(' : ', alignment=(0.5, 0.5))
        hbox = gtk.HBox()
        hbox.pack_end(label_status, False, False)
        hbox.pack_end(label_sep, False, False)
        hbox.pack_end(label_en, False, False)
        eb.add(hbox)
        return eb

    def register_callbacks(self, window):
        window.connect('key-press-event', self.key_press_callback)
        window.add_events(gtk.gdk.KEY_PRESS_MASK)
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gtk.gdk.KEY_RELEASE_MASK)

    def locate_audio_sample(self, path):
        if path is None:
            raise error.TestFail('ERROR: Must provide an audio sample')
        if not os.path.isabs(path):
            # Assume the relative path is based in autotest directory.
            path = os.path.join(self.job.autodir, path)
        if not os.path.exists(path):
            raise error.TestFail('ERROR: Unable to find audio sample %s' % path)
        return path

    def run_once(self, audio_sample_path=None, audio_init_volume=None):

        factory.log('%s run_once' % self.__class__)

        # Change initial volume.
        if audio_init_volume:
            os.system("amixer -c 0 sset Master %d%%" % audio_init_volume)

        # Write recordings in tmpdir.
        os.chdir(self.tmpdir)

        self._bg_job = None
        self._audio_sample_path = self.locate_audio_sample(audio_sample_path)

        self._sample_queue = [x for x in reversed(_SAMPLE_LIST)]
        self._status_map = dict((n, ful.UNTESTED) for n in _SAMPLE_LIST)
        # Ensure that we don't try to handle multiple overlapping
        # keypress actions. Make a note of when we are currently busy
        # and refuse events during that time.
        self._active = False

        prompt_label = ful.make_label(_LABEL_START_STR, alignment=(0.5, 0.5))

        self._top_level_test_list = gtk.VBox()
        self._top_level_test_list.pack_start(prompt_label, False, False)

        for name in _SAMPLE_LIST:
            label_box = self.make_sample_label_box(name)
            self._top_level_test_list.pack_start(label_box, False, False)

        self._test_widget = gtk.EventBox()
        self._test_widget.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        self._test_widget.add(self._top_level_test_list)

        self._subtest_widget = None

        self.goto_next_sample()

        ful.run_test_widget(self.job, self._test_widget,
            window_registration_callback=self.register_callbacks)

        failed_set = set(name for name, status in self._status_map.items()
                         if status is not ful.PASSED)
        if failed_set:
            raise error.TestFail('some samples failed (%s)' %
                                 ', '.join(failed_set))

        factory.log('%s run_once finished' % self.__class__)
