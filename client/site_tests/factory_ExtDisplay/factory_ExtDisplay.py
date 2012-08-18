# -*- coding: utf-8 -*-
#
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This is a factory test to test the external display (hdmi/vga/other)
# UI based heavily on factory_Display/factory_Audio


import gobject
import gtk
import logging
import os
import pango
import sys

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.cros import factory_setup_modules
from cros.factory.test import factory
from cros.factory.test import ui as ful


_LABEL_STATUS_SIZE = (140, 30)
_LABEL_START_STR_AUDIO = 'Connect headset.\n'
_LABEL_START_STR = 'Connect external display\n\nhit SPACE to start test.'
_LABEL_RESPONSE_STR = ful.USER_PASS_FAIL_SELECT_STR + '\n'
_VERBOSE = False

_SUBTEST_LIST = [
    ('External Display Video',
     {'msg' : 'Do you see video on External Display\n' + \
          '请检查外接萤幕是否有显示画面\n\n' + \
          _LABEL_RESPONSE_STR,
      'cfg_disp' : True,
      }),
    ]
_OPTIONAL = ('External Display Audio',
             {'msg' : 'Do you hear audio from External Display\n' + \
                  '请检查是否有听到声音\n\n' + \
                  _LABEL_RESPONSE_STR,
              'cfg':['amixer -c 0 cset name="IEC958 Playback Switch" on'],
              'cmd':'aplay -q',
              'postcfg':['amixer -c 0 cset name="IEC958 Playback Switch" off'],
              })
_CLEANUP = ('Disconnect Display',
            {'msg':'Disconnect external display\n' + \
                 '移除外接萤幕\n\n' + \
                 'Or press TAB to fail\n' + \
                 '若无法通过测试请按TAB',
                 'disp_off' : True,
                 'cond':'[ $(xrandr -d :0 | grep " connected" | wc -l) == "1" ]'
            })

class factory_ExtDisplay(test.test):
    version = 1

    def close_bgjob(self, name):
        job = self._job
        if job:
            utils.nuke_subprocess(job.sp)
            utils.join_bg_jobs([job], timeout=1)
            result = job.result
            if _VERBOSE and (result.stdout or result.stderr):
                raise error.CmdError(
                    name, result,
                    'stdout: %s\nstderr: %s' % (result.stdout, result.stderr))
        self._job = None

    def goto_next_subtest(self):
        if not self._subtest_queue:
            gtk.main_quit()
            return
        self._current_subtest = self._subtest_queue.pop()
        name, cfg = self._current_subtest
        self.update_status(name, ful.ACTIVE)

    def start_subtest(self):
        subtest_name, subtest_cfg = self._current_subtest
        if 'cfg' in subtest_cfg:
            for cfg in subtest_cfg['cfg']:
                try:
                    utils.system(cfg)
                except error.CmdError:
                    raise error.TestNAError('Setup failed\nCmd: %s' % cfg)
                factory.log("cmd: " + cfg)
        if 'cond' in subtest_cfg:
            self._timer = gobject.timeout_add(500, self.timer_callback)
        if 'cfg_disp' in subtest_cfg:
            if (self._main_display is not None and
                self._ext_display is not None):
                cmd = ((
                    'while [ $(xrandr -d :0 | grep "^%s connected" | wc -l) ' +
                    '        == "0" ]; do sleep 0.5; done; ' +
                    'xrandr -d :0 --output %s --auto --crtc 0 ' +
                    '--output %s --auto --crtc 1') %
                    (self._ext_display, self._main_display, self._ext_display))
                factory.log("cmd: " + cmd)
                self._job = utils.BgJob(cmd, stderr_level=logging.DEBUG)
        elif 'cmd' in subtest_cfg:
            cmd = "%s %s" % (subtest_cfg['cmd'], self._sample)
            factory.log("cmd: " + cmd)
            self._job = utils.BgJob(cmd, stderr_level=logging.DEBUG)
        elif 'disp_off' in subtest_cfg:
            if (self._ext_display is not None):
                cmd = "xrandr -d :0 --output %s --off" % (self._ext_display)
                factory.log("cmd: " + cmd)
                self._job = utils.BgJob(cmd, stderr_level=logging.DEBUG)
        else:
            self._job = None

    def finish_subtest(self):
        subtest_name, subtest_cfg = self._current_subtest
        if 'postcfg' in subtest_cfg:
            for cfg in subtest_cfg['postcfg']:
                try:
                    utils.system(cfg)
                except error.CmdError:
                    raise error.TestNAError('Setup failed\nCmd: %s' % cfg)
                factory.log("cmd: " + cfg)
        self.close_bgjob(subtest_cfg)
        if self._timer is not None:
            gobject.source_remove(self._timer)
            self._timer = None

    def key_press_callback(self, widget, event):
        subtest_name, subtest_cfg = self._current_subtest
        if event.keyval == gtk.keysyms.space and not self._started:
            self.start_subtest()
            self._prompt_label.set_text(subtest_cfg['msg'])
            self._started = True
            self._test_widget.queue_draw()
        return True

    def key_release_callback(self, widget, event):
        if not self._started:
            return True
        subtest_name, subtest_cfg = self._current_subtest
        if event.keyval == gtk.keysyms.Tab and \
                self._status_map[subtest_name] is ful.ACTIVE:
            self.update_status(subtest_name, ful.FAILED)
            self.finish_subtest()
            self.goto_next_subtest()
        elif event.keyval == gtk.keysyms.Return and \
                self._status_map[subtest_name] is ful.ACTIVE and \
                'cond' not in subtest_cfg:
            self.update_status(subtest_name, ful.PASSED)
            self.finish_subtest()
            self.goto_next_subtest()
        elif event.keyval == ord('Q'):
            gtk.main_quit()

        # evaluating a new subtest now
        if subtest_name is not self._current_subtest[0]:
            subtest_name, subtest_cfg = self._current_subtest
            self.start_subtest()
            self._prompt_label.set_text(subtest_cfg['msg'])

        self._test_widget.queue_draw()
        return True

    def timer_callback(self):
        subtest_name, subtest_cfg = self._current_subtest
        cond = subtest_cfg['cond']
        exit_code = utils.system(command=cond, ignore_status=True)
        if exit_code == 0:
            self.update_status(subtest_name, ful.PASSED)
            self.finish_subtest()
            self.goto_next_subtest()
            self._test_widget.queue_draw()
            return False
        return True

    def update_status(self, name, status):
        self._status_map[name] = status
        self._label_status[name].set_text(status)
        self._label_status[name].modify_fg(gtk.STATE_NORMAL,
                                           ful.LABEL_COLORS[status])
        self._label_status[name].queue_draw()

    def make_subtest_label_box(self, name):
        eb = gtk.EventBox()
        eb.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        label_status = ful.make_label(ful.UNTESTED, size=_LABEL_STATUS_SIZE,
                                  alignment=(0, 0.5),
                                      fg=ful.LABEL_COLORS[ful.UNTESTED])
        self._label_status[name] = label_status
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
        if not path:
            raise error.TestFail('ERROR: Must provide an audio sample')
        if not os.path.isabs(path):
             # Assume the relative path is based in autotest directory.
            path = os.path.join(self.autodir, path)
        if not os.path.exists(path):
            raise error.TestFail('ERROR: Unable to find audio sample %s' % path)
        self._sample = path

    def run_once(self,
                 has_audio=False,
                 audio_sample_path=None,
                 main_display=None,
                 ext_display=None):

        factory.log('%s run_once' % self.__class__)

        # Src contains the audio files.
        os.chdir(self.autodir)

        self._main_display = main_display
        self._ext_display = ext_display

        self._started = False
        self._timer = None

        if has_audio:
            self.locate_audio_sample(audio_sample_path)
            _SUBTEST_LIST.append(_OPTIONAL)
        _SUBTEST_LIST.append(_CLEANUP)

        self._subtest_queue = [x for x in reversed(_SUBTEST_LIST)]
        self._status_map = dict((n, ful.UNTESTED) for n, c in _SUBTEST_LIST)
        self._label_status = dict()


        if has_audio:
            label_start = _LABEL_START_STR_AUDIO + _LABEL_START_STR
        else:
            label_start = _LABEL_START_STR
        prompt_label = ful.make_label(label_start, fg=ful.WHITE)
        self._prompt_label = prompt_label

        vbox = gtk.VBox()
        vbox.pack_start(prompt_label, False, False)

        for name, cfg in _SUBTEST_LIST:
            label_box = self.make_subtest_label_box(name)
            vbox.pack_start(label_box, False, False)

        self._test_widget = vbox

        self.goto_next_subtest()

        ful.run_test_widget(self.job, vbox,
            window_registration_callback=self.register_callbacks)

        failed_set = set(name for name, status in self._status_map.items()
                         if status is not ful.PASSED)
        if failed_set:
            raise error.TestFail('some subtests failed (%s)' %
                                 ', '.join(failed_set))

        factory.log('%s run_once finished' % self.__class__)
