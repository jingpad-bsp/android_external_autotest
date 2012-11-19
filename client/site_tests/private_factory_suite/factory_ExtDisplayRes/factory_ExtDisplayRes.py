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
import StringIO

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.cros import factory_setup_modules
from cros.factory.test import factory
from cros.factory.test import ui as ful


_LABEL_STATUS_SIZE = (140, 30)
_LABEL_START_STR_AUDIO = 'Connect headset.\n'
_LABEL_START_STR = 'Connect external display\n\nhit SPACE to start test.'
_LABEL_RESPONSE_STR = ful.USER_PASS_FAIL_SELECT_STR
_VERBOSE = False

_SUBTEST_LIST = [
    ('Wait For External Display ',
     {'msg' : 'Plug in External Display\n' + \
         _LABEL_RESPONSE_STR,
        'cond': 'connected',
     }),
    ('External Display Video',
     {'msg' : 'Do you see video on External Display?\n' + \
          _LABEL_RESPONSE_STR,
      'cfg_disp' : True,
      }),
    ('\t1920x1200',
     {'msg' : 'Do you see video on External Display? \n' + \
          'Hit esc to update display list then confirm resolution\n\n' + \
          _LABEL_RESPONSE_STR,
      'res' : '1920x1200',
      'cfg_disp' : True,
      }),
    ('\t640x480',
     {'msg' : 'Do you see video on External Display? \n' + \
          'Hit esc to update display list and confirm resolution\n\n' + \
          _LABEL_RESPONSE_STR,
      'res' : '640x480',
      'cfg_disp' : True,
      }),
    ('\t1920x1080',
     {'msg' : 'Do you see video on External Display? \n' + \
          'Hit esc to update display list and confirm resolution\n\n' + \
          _LABEL_RESPONSE_STR,
      'res' : '1920x1080',
      'cfg_disp' : True,
      }),
    ('Turn off external display',
     {'msg' : 'Has External display gone black?\n' + \
          _LABEL_RESPONSE_STR,
        'disp_off' : True,
      }),
    ]
_CLEANUP = ('Disconnect Display',
            {'msg':'Disconnect external display\n' + \
                 'Or press TAB to fail\n',
                 'cond' : 'disconnected',
            })

class factory_ExtDisplayRes(test.test):
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

    def start_display(self, main, ext):
        """  Pushes image to external display. """
        cmd = ((
            'while [ $(xrandr -d :0 | grep "^%s connected" | wc -l) ' +
            '        == "0" ]; do sleep 0.5; done; ' +
            'xrandr -d :0 --output %s --auto --crtc 0 ' +
            '--output %s --auto --crtc 1') %
            (ext, main, ext))
        self._job = utils.BgJob(cmd, stderr_level=logging.DEBUG)

    def stop_display(self, ext):
        """ Disconnects external display. """
        cmd = "xrandr -d :0 --output %s --off" % (ext)
        self._job = utils.BgJob(cmd, stderr_level=logging.DEBUG)

    def set_resolution(self, ext, res):
        """ Sets resolution of external display """
        cmd = "xrandr -d :0 --output %s --mode %s" % (ext, res)
        self._job = utils.BgJob(cmd, stderr_level=logging.DEBUG)

    def list_connected_displays(self):
        """ Lists characteristics of connected displays. """
        pipein, pipeout = os.pipe()
        cmd = 'xrandr -d :0 | grep " connected"'
        self._job = utils.BgJob(cmd, stdin=pipeout)
        self._job.output_prepare(StringIO.StringIO(), StringIO.StringIO())
        self._job.process_output(stdout=True, final_read=True)

        para = self._job.sp.stdout.readlines()
        vbox = self._test_widget
        verse = ''
        for line in para:
            l1, l2 = line.split('(')
            l2, l3 = l2.split(')')
            verse += '\n' + l1 + '\n\t' + l2 + '\n\t' + l3 + '\n'

        if self._display_list is not None:
            self._test_widget.remove(self._display_list)
        self._display_list = ful.make_label(verse, fg=ful.RED)
        vbox.pack_start(self._display_list, False, False)
        vbox.show_all()

    def get_wait_condition(self, cond):
        """ Returns wait condition based on input parameters. """
        subtest_name, subtest_cfg = self._current_subtest
        xrandr_str = 'xrandr -d :0'
        grep_str = 'grep "^%s %s"' % (self._ext_display, cond)
        wc_str = 'wc -l'
        return '[ $('+xrandr_str + '|' + grep_str + '|' + wc_str + ') == "1" ]'

    def start_subtest(self):
        subtest_name, subtest_cfg = self._current_subtest
        if 'cfg' in subtest_cfg:
            for cfg in subtest_cfg['cfg']:
                try:
                    utils.system(cfg)
                except error.CmdError:
                    raise error.TestNAError('Setup failed\nCmd: %s' % cfg)
                factory.log("cmd: " + cfg)
        cond = subtest_cfg.get('cond')
        if cond is not None:
            subtest_cfg.update({'wait_cond' : self.get_wait_condition(cond)})
            self._timer = gobject.timeout_add(500, self.timer_callback)
        if 'cfg_disp' in subtest_cfg:
            if (self._main_display is not None and
                self._ext_display is not None):
                res = subtest_cfg.get('res')
                if res is not None:
                    self.set_resolution(self._ext_display, res)
                else:
                    self.start_display(self._main_display, self._ext_display)
        elif 'cmd' in subtest_cfg:
            cmd = "%s %s" % (subtest_cfg['cmd'], self._sample)
            factory.log("cmd: " + cmd)
            self._job = utils.BgJob(cmd, stderr_level=logging.DEBUG)
        elif 'disp_off' in subtest_cfg:
            if (self._ext_display is not None):
                self.stop_display(self._ext_display)
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

    def start_next_subtest(self, current_test_status):
        """ Main routine for iterating over the sub test list. """
        subtest_name, subtest_cfg = self._current_subtest
        self.update_status(subtest_name, current_test_status)
        self.finish_subtest()
        self.goto_next_subtest()

        # evaluating a new subtest now
        if subtest_name is not self._current_subtest[0]:
            subtest_name, subtest_cfg = self._current_subtest
            self.start_subtest()
            self._prompt_label.set_text(subtest_cfg['msg'])
        self._test_widget.queue_draw()

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
            self.start_next_subtest(ful.FAILED)
        elif event.keyval == gtk.keysyms.Return and \
                self._status_map[subtest_name] is ful.ACTIVE and \
                'cond' not in subtest_cfg:
            self.list_connected_displays()
            self.start_next_subtest(ful.PASSED)
        elif event.keyval == ord('Q'):
            gtk.main_quit()
        self.list_connected_displays()
        return True

    def timer_callback(self):
        subtest_name, subtest_cfg = self._current_subtest
        cond = subtest_cfg.get('wait_cond')
        factory.log('waiting for cond: '+cond)
        exit_code = utils.system(command=cond, ignore_status=True)
        if exit_code == 0:
            if subtest_cfg.get('cond') is 'disconnect':
                self.update_status(subtest_name, ful.PASSED)
                self.finish_subtest()
                self.goto_next_subtest()
                self._test_widget.queue_draw()
                return False
            else:
                self.start_next_subtest(ful.PASSED)
        self.list_connected_displays()
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

    def run_once(self,
                 has_audio=False,
                 audio_sample_path=None,
                 main_display=None,
                 ext_display=None):

        factory.log('%s run_once' % self.__class__)

        os.chdir(self.autodir)

        self._main_display = main_display
        self._ext_display = ext_display
        self._display_list = None

        self._started = False
        self._timer = None

        _SUBTEST_LIST.append(_CLEANUP)

        self._subtest_queue = [x for x in reversed(_SUBTEST_LIST)]
        self._status_map = dict((n, ful.UNTESTED) for n, c in _SUBTEST_LIST)
        self._label_status = dict()

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
