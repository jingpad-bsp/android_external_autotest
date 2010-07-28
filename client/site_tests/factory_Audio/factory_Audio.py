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
from autotest_lib.client.common_lib import error, utils


_LABEL_BIG_SIZE = (280, 60)
_LABEL_STATUS_SIZE = (140, 30)
_LABEL_START_STR = 'hit SPACE to start each audio test\n' +\
    '按空白鍵開始各項聲音測試\n\n'
_LABEL_RESPONSE_STR = ful.USER_PASS_FAIL_SELECT_STR + '\n'
_SAMPLE_LIST = ['Headset Audio Test', 'Built-in Audio Test']
_VERBOSE = False


# FIXME: tbroch : refactor from factory_ui -> factory_ui_lib.py
_SEP_COLOR = gtk.gdk.color_parse('grey50')
def make_vsep(width=1):
    frame = gtk.EventBox()
    frame.set_size_request(width, -1)
    frame.modify_bg(gtk.STATE_NORMAL, _SEP_COLOR)
    return frame

def make_hsep(width=1):
    frame = gtk.EventBox()
    frame.set_size_request(-1, width)
    frame.modify_bg(gtk.STATE_NORMAL, _SEP_COLOR)
    return frame


class factory_Audio(test.test):
    version = 1


    def audio_subtest_widget(self, name):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        screen = window.get_screen()
        screen_size = (screen.get_width(), screen.get_height())
        window.set_size_request(*self._test_widget_size)

        vb = gtk.VBox()
        ebh = gtk.EventBox()
        ebh.modify_bg(gtk.STATE_NORMAL, ful.LABEL_COLORS[ful.ACTIVE])
        ebh.add(ful.make_label(name, size=_LABEL_BIG_SIZE,
                               fg=ful.BLACK))
        vb.pack_start(ebh)
        vb.pack_start(make_vsep(3), False, False)
        if re.search('Headset', name):
            lab_str = 'Connect headset to device\n將耳機接上音源孔'
        else:
            lab_str = 'Remove headset from device\n將耳機移開音源孔'
        vb.pack_start(ful.make_label(lab_str, fg=ful.WHITE))
        vb.pack_start(make_vsep(3), False, False)
        vb.pack_start(ful.make_label(\
                'Press & hold \'r\' to record\n壓住 \'r\' 鍵開始錄音\n' + \
                    '[Playback will follow]\n[之後會重播錄到的聲音]\n\n' + \
                    'Press & hold \'p\' to play sample\n' + \
                    '壓住 \'p\' 鍵以播放範例'))
        vb.pack_start(make_vsep(3), False, False)
        vb.pack_start(ful.make_label(ful.USER_PASS_FAIL_SELECT_STR,
                                     fg=ful.WHITE))

        # need event box to effect bg color
        eb = gtk.EventBox()
        eb.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        eb.add(vb)
        window.add(eb)
        window.show_all()
        self._fs_window = window

    def close_bgjob(self, sample_name):
        job = self._job
        if job:
            utils.nuke_subprocess(job.sp)
            utils.join_bg_jobs([job], timeout=1)
            result = job.result
            if _VERBOSE and (result.stdout or result.stderr):
                raise error.CmdError(
                    sample_name, result,
                    'stdout: %s\nstderr: %s' % (result.stdout, result.stderr))
        self._job = None

    def goto_next_sample(self):
        if not self._sample_queue:
            gtk.main_quit()
            return
        self._current_sample = self._sample_queue.pop()
        name = self._current_sample
        self._status_map[name] = ful.ACTIVE

    def cleanup_sample(self):
        factory.log('Inside cleanup_sample')
        self._fs_window.destroy()
        self._fs_window = None
        self.goto_next_sample()

    def key_press_callback(self, widget, event):
        name = self._current_sample
        if event.keyval == gtk.keysyms.space and not self._fs_window:
            # start the subtest
            self.audio_subtest_widget(name)
        else:
            self.close_bgjob(name)
            cmd = None
            if event.keyval == ord('r'):
                # record via mic
                if os.path.isfile('rec.wav'):
                    os.unlink('rec.wav')
                cmd = 'arecord -f dat -t wav rec.wav'
            elif event.keyval == ord('p'):
                # playback canned audio
                cmd = 'aplay %s' % self._sample
            if cmd:
                self._job = utils.BgJob(cmd, stderr_level=logging.DEBUG)
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
            self._job = utils.BgJob(cmd, stderr_level=logging.DEBUG)
            factory.log("cmd: " + cmd)
        elif event.keyval == ord('p'):
            self.close_bgjob(name)
        else:
            self._ft_state.exit_on_trigger(event)

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

    def locate_asample(self, sample):
        if not sample:
            raise error.TestFail('ERROR: Must provide an audio sample')
        if not os.path.isabs(sample):
            # assume its in deps
            sample = self.autodir + '/' + sample
        if not os.path.exists(sample):
            raise error.TestFail('ERROR: Unable to find audio sample %s' \
                                     % sample)
        self._sample=sample

    def run_once(self,
                 test_widget_size=None,
                 trigger_set=None,
                 sample=None,
                 ):

        factory.log('%s run_once' % self.__class__)

        self._job = None
        self._test_widget_size = test_widget_size
        self.locate_asample(sample)
        # to write the recordings
        os.chdir(self.tmpdir)

        xset_status = os.system('LD_LIBRARY_PATH=/usr/local/lib xset r off')
        if xset_status:
            raise error.TestFail('ERROR: disabling key repeat')

        self._ft_state = ful.State(trigger_set=trigger_set)

        self._sample_queue = [x for x in reversed(_SAMPLE_LIST)]
        self._status_map = dict((n, ful.UNTESTED) for n in _SAMPLE_LIST)

        prompt_label = ful.make_label(_LABEL_START_STR, alignment=(0.5, 0.5))

        vbox = gtk.VBox()
        vbox.pack_start(prompt_label, False, False)

        for name in _SAMPLE_LIST:
            label_box = self.make_sample_label_box(name)
            vbox.pack_start(label_box, False, False)

        test_widget = gtk.EventBox()
        test_widget.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        test_widget.add(vbox)
        self._test_widget = test_widget

        self.goto_next_sample()

        self._fs_window = None

        self._ft_state.run_test_widget(
            test_widget=test_widget,
            test_widget_size=test_widget_size,
            window_registration_callback=self.register_callbacks)

        failed_set = set(name for name, status in self._status_map.items()
                         if status is not ful.PASSED)
        if failed_set:
            raise error.TestFail('some samples failed (%s)' %
                                 ', '.join(failed_set))

        factory.log('%s run_once finished' % self.__class__)
