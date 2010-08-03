# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This is a factory test to test the external display (hdmi/vga/other)
# UI based heavily on factory_Display/factory_Audio


import gtk
import logging
import os
import pango
import sys

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils


_LABEL_STATUS_SIZE = (140, 30)
_LABEL_START_STR = 'Connect headset.\n(Chinese)\n' + \
    'Connect external display\n(Chinese)\n\nhit SPACE to start test.'
_LABEL_RESPONSE_STR = ful.USER_PASS_FAIL_SELECT_STR + '\n'
_VERBOSE = False

_SUBTEST_LIST = [
    ('External Display Video',
     {'msg' : 'Do you see video on External Display\n\n' + \
          _LABEL_RESPONSE_STR,
      }),
    ]
_OPTIONAL = ('External Display Audio',
             {'msg' : 'Do you hear audio from External Display\n\n' + \
                  _LABEL_RESPONSE_STR,
              'cfg':['amixer -c 0 cset name="IEC958 Playback Switch" on'],
              'cmd':'aplay -q',
              'postcfg':['amixer -c 0 cset name="IEC958 Playback Switch" off'],
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
        self._status_map[name] = ful.ACTIVE

    def start_subtest(self):
        subtest_name, subtest_cfg = self._current_subtest
        if 'cfg' in subtest_cfg:
            for cfg in subtest_cfg['cfg']:
                utils.system(cfg)
                factory.log("cmd: " + cfg)
        if 'cmd' in subtest_cfg:
            cmd = "%s %s" % (subtest_cfg['cmd'], self._sample)
            factory.log("cmd: " + cmd)
            self._job = utils.BgJob(cmd, stderr_level=logging.DEBUG)
        else:
            self._job = None

    def finish_subtest(self):
        subtest_name, subtest_cfg = self._current_subtest
        if 'postcfg' in subtest_cfg:
            for cfg in subtest_cfg['postcfg']:
                utils.system(cfg)
                factory.log("cmd: " + cfg)
        self.close_bgjob(subtest_cfg)

    def key_press_callback(self, widget, event):
        subtest_name, subtest_cfg = self._current_subtest
        if event.keyval == gtk.keysyms.space and not self._started:
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
            self._status_map[subtest_name] = ful.FAILED
            self.finish_subtest()
            self.goto_next_subtest()
        elif event.keyval == gtk.keysyms.Return and \
                self._status_map[subtest_name] is ful.ACTIVE:
            self._status_map[subtest_name] = ful.PASSED
            self.finish_subtest()
            self.goto_next_subtest()
        elif event.keyval == ord('Q'):
            gtk.main_quit()
        else:
            self._ft_state.exit_on_trigger(event)

        # evaluating a new subtest now
        if subtest_name is not self._current_subtest[0]:
            subtest_name, subtest_cfg = self._current_subtest
            self.start_subtest()
            self._prompt_label.set_text(subtest_cfg['msg'])

        self._test_widget.queue_draw()
        return True

    def label_status_expose(self, widget, event, name=None):
        status = self._status_map[name]
        widget.set_text(status)
        widget.modify_fg(gtk.STATE_NORMAL, ful.LABEL_COLORS[status])

    def make_subtest_label_box(self, name):
        eb = gtk.EventBox()
        eb.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        label_status = ful.make_label(ful.UNTESTED, size=_LABEL_STATUS_SIZE,
                                  alignment=(0, 0.5),
                                      fg=ful.LABEL_COLORS[ful.UNTESTED])
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
                 has_audio=False,
                 sample=None,
                 ):

        factory.log('%s run_once' % self.__class__)
        # because audio files relative to that
        os.chdir(self.autodir)

        self._ft_state = ful.State(trigger_set=trigger_set)
        self._test_widget_size = test_widget_size
        self._started = False

        if has_audio:
            self.locate_asample(sample)
            _SUBTEST_LIST.append(_OPTIONAL)

        self._subtest_queue = [x for x in reversed(_SUBTEST_LIST)]
        self._status_map = dict((n, ful.UNTESTED) for n, c in _SUBTEST_LIST)


        prompt_label = ful.make_label(_LABEL_START_STR, fg=ful.WHITE)
        self._prompt_label = prompt_label

        vbox = gtk.VBox()
        vbox.pack_start(prompt_label, False, False)

        for name, cfg in _SUBTEST_LIST:
            label_box = self.make_subtest_label_box(name)
            vbox.pack_start(label_box, False, False)

        self._test_widget = vbox

        self.goto_next_subtest()
        self.start_subtest()

        self._ft_state.run_test_widget(
            test_widget=vbox,
            test_widget_size=test_widget_size,
            window_registration_callback=self.register_callbacks)

        failed_set = set(name for name, status in self._status_map.items()
                         if status is not ful.PASSED)
        if failed_set:
            raise error.TestFail('some subtests failed (%s)' %
                                 ', '.join(failed_set))

        factory.log('%s run_once finished' % self.__class__)
