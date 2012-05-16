# -*- coding: utf-8 -*-
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION : factory test of ambient light sensor.  Test that ALS reacts to
# both darkening by covering w/ finger as well as brightening.
# Roughly speaking:
# indoor ambient lighting: 20-100
# sunlight direct: 30k-60k
# flashlight direct: 5k-10k


import gobject
import gtk
import logging
import math
import os
import sys
import time

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import ui as ful

_LABEL_STATUS_SIZE = (140, 30)

_DEFAULT_SUBTEST_LIST = ['Light sensor dark',
                         'Light sensor exact',
                         'Light sensor light']
_DEFAULT_SUBTEST_CFG = {'Light sensor dark': {'below': 4},
                        'Light sensor exact': {'between': (10, 15)},
                        'Light sensor light': {'above': 200}}
_DEFAULT_SUBTEST_INSTRUCTION = {
    'Light sensor dark': 'Cover light sensor with finger',
    'Light sensor exact': 'Remove finger from light sensor',
    'Light sensor light': 'Shine light sensor with flashlight'}
_DEFAULT_DEVICE_PATH='/sys/bus/iio/devices/devices0/'

class iio_generic():
    '''
    Object to interface to ambient light sensor over iio.
    '''
    PARAMS = {'rd': _DEFAULT_DEVICE_PATH + 'illuminance0_input',
              'init': '',
              'min': 0,
              'max': math.pow(2, 16),
              # in seconds
              'mindelay': 0.178,
              }

    def __init__(self, device_path):
        self.buf = []
        self.ambient = None

        if device_path is not None:
            self.PARAMS['rd'] = device_path + 'illuminance0_input'

        if not os.path.isfile(self.PARAMS['rd']):
            self.cfg()

        self.ambient = self.read('mean', delay=0, samples=10)
        factory.log('ambient light sensor = %d' % self.ambient)

    def cfg(self):
        cmd = self.PARAMS['init']
        utils.system(cmd)
        time.sleep(1)
        if not os.path.isfile(self.PARAMS['rd']):
            raise error.TestError(cmd + ' did not create ' + self.PARAMS['rd'])
        val = self.read('first', samples=1)
        if val <= self.PARAMS['min'] or val >= self.PARAMS['max']:
            raise error.TestError('Failed initial read\n')


    def read(self, type, delay=None, samples=1):
        '''
        Read the light sensor and return value based on type
        @parameter type - string describing type of value to return.  Valid
        strings are 'mean' | 'min' | 'max' | 'raw'
        @parameter delay - delay between samples in seconds.  0 means as fast as
        possible
        @parameter samples - total samples to read.  O means infinite
        '''
        cnt = 0
        self.buf = []
        if delay is None:
            delay = self.PARAMS['mindelay']
        while True:
            fd = open(self.PARAMS['rd'])
            ln = int(fd.readline().rstrip())
            fd.close()
            self.buf.append(ln)
            cnt += 1
            time.sleep(delay)
            if cnt == samples:
                break
        if type is 'mean':
            return sum(self.buf) / len(self.buf)
        elif type is 'max':
            return max(self.buf)
        elif type is 'min':
            return min(self.buf)
        elif type is 'raw':
            return self.buf
        elif type is 'first':
            return self.buf[0]
        else:
            error.ValueError('Illegal value %s for type' % type)


class factory_LightSensor(test.test):
    version = 3

    def next_subtest(self):
        self._tested += 1
        if self._tested >= len(self._subtest_list):
            gtk.main_quit()
            return False
        self._active_subtest = self._subtest_list[self._tested]
        self._status_map[self._active_subtest] = ful.ACTIVE
        self._status_label[self._active_subtest].queue_draw()
        self._deadline = time.time() + self._timeout_per_subtest
        self._current_iter_remained = self._iter_req_per_subtest
        self._cumulative_val = 0
        return True

    def timer_event(self, countdown_label):
        time_remaining = max(0, self._deadline - time.time())
        if time_remaining is 0:
            self._status_map[self._active_subtest] = ful.FAILED
            self._status_label[self._active_subtest].queue_draw()
            factory.log('Timeout on subtest "%s"' % self._active_subtest)
            if not self.next_subtest():
                return True

        countdown_label.set_text('%d' % time_remaining)
        countdown_label.queue_draw()
        return True

    def key_release_callback(self, widget, event):
        if event.keyval == ord('Q'):
            gtk.main_quit()
            return True
        if event.keyval == ord(' ') and not self._started:
            self._started = True
            self._active_subtest = self._subtest_list[0]
            self._status_map[self._active_subtest] = ful.ACTIVE
            self._status_label[self._active_subtest].queue_draw()
            self._deadline = time.time() + self._timeout_per_subtest
            gobject.timeout_add(1000, self.timer_event, self._countdown_label)

        return True

    def pass_one_iter(self, name):
        self._current_iter_remained -= 1
        if self._current_iter_remained is 0:
            self._status_map[name] = ful.PASSED
            self._status_label[name].queue_draw()
            self._current_iter_remained = self._iter_req_per_subtest
            mean_val = self._cumulative_val / self._iter_req_per_subtest
            factory.log('Passed subtest "%s" with mean value %d.' %
                        (name, mean_val))
            if not self.next_subtest():
                return

    def sensor_event(self, sensor_value):
        val = self._als.read('mean', samples=5, delay=0)

        if self._started:
            name = self._active_subtest
            cfg = self._subtest_cfg[name]
            passed = 0
            if 'above' in cfg:
                if val > cfg['above']:
                    factory.log('Passed checking "above" %d > %d' %
                                (val, cfg['above']))
                    passed = 1
            elif 'below' in cfg:
                if val < cfg['below']:
                    factory.log('Passed checking "below" %d < %d' %
                                (val, cfg['below']))
                    passed = 1
            elif 'between' in cfg:
                lb, ub = cfg['between']
                if val > lb and val < ub:
                    factory.log('Passed checking "between" %d < %d < %d' %
                                (lb, val, ub))
                    passed = 1
            if passed is 1:
                self._cumulative_val += val
                self.pass_one_iter(name)
            else:
                if self._current_iter_remained != self._iter_req_per_subtest:
                    factory.log('Resetting iter count.')
                self._cumulative_val = 0
                self._current_iter_remained = self._iter_req_per_subtest

        sensor_value.set_text('%d' % val)
        sensor_value.queue_draw()
        return True

    def label_status_expose(self, widget, event, name):
        status = self._status_map[name]
        widget.set_text(status)
        widget.modify_fg(gtk.STATE_NORMAL, ful.LABEL_COLORS[status])
        return False

    def calc_cfg_description(self, cfg):
        if 'above' in cfg:
            return 'Input > %d' % cfg['above']
        elif 'below' in cfg:
            return 'Input < %d' % cfg['below']
        elif 'between' in cfg:
            return '%d < Input < %d' % cfg['between']
        else:
            raise error.ValueError('Unknown type in subtest configuration')

    def make_subtest_label_box(self, name):
        eb = gtk.EventBox()
        eb.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        label_status = ful.make_label(ful.UNTESTED, size=_LABEL_STATUS_SIZE,
                                      alignment=(0, 0.5),
                                      fg=ful.LABEL_COLORS[ful.UNTESTED])
        label_status.connect('expose_event', self.label_status_expose, name)
        label_desc = ful.make_label(self._subtest_instruction[name],
                                    alignment=(0.5, 0.5), fg=ful.WHITE)
        cfg_desc = self.calc_cfg_description(self._subtest_cfg[name])
        label_en = ful.make_label("%s (%s)" % (name, cfg_desc),
                                  alignment=(1, 0.5))
        label_sep = ful.make_label(' : ', alignment=(0.5, 0.5))
        hbox = gtk.HBox()
        hbox.pack_end(label_status, False, False)
        hbox.pack_end(label_sep, False, False)
        hbox.pack_end(label_en, False, False)
        vbox = gtk.VBox()
        vbox.pack_start(label_desc, False, False)
        vbox.pack_start(hbox, False, False)
        eb.add(vbox)
        return eb

    def register_callbacks(self, window):
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gtk.gdk.KEY_RELEASE_MASK)

    def get_subtest(self, subtest_list, subtest_cfg, subtest_instruction):
        has_specified = (subtest_list is not None or
                         subtest_cfg is not None or
                         subtest_instruction is not None)
        all_specified = (subtest_list is not None and
                         subtest_cfg is not None and
                         subtest_instruction is not None)
        if has_specified and not all_specified:
            raise error.ValueError('Missing parameters of subtests.')
        if all_specified:
            self._subtest_list = subtest_list
            self._subtest_cfg = subtest_cfg
            self._subtest_instruction = subtest_instruction
        else:
            self._subtest_list = _DEFAULT_SUBTEST_LIST
            self._subtest_cfg = _DEFAULT_SUBTEST_CFG
            self._subtest_instruction = _DEFAULT_SUBTEST_INSTRUCTION

    def run_once(self,
                 device_path=None,
                 timeout_per_subtest=10,
                 subtest_list=None,
                 subtest_cfg=None,
                 subtest_instruction=None):

        factory.log('%s run_once' % self.__class__)

        self.get_subtest(subtest_list, subtest_cfg, subtest_instruction)

        self._als = iio_generic(device_path)

        self._timeout_per_subtest = timeout_per_subtest

        self._iter_req_per_subtest = 3
        self._current_iter_remained = self._iter_req_per_subtest
        self._cumulative_val = 0

        self._status_map = dict((n, ful.UNTESTED) for n in self._subtest_list)
        self._tested = 0

        self._started = False

        vbox = gtk.VBox()
        prompt_label = ful.make_label(
            'Use indicated light source to pass each subtest\n'
            'Hit "space" to begin...\n',
            fg=ful.WHITE)
        vbox.pack_start(prompt_label, False, False)

        padding_size = 15

        self._status_label = {}
        for name in self._subtest_list:
            label_box = self.make_subtest_label_box(name)
            vbox.pack_start(label_box, False, False, padding_size)
            self._status_label[name] = label_box

        vbox.pack_start(ful.make_hsep(), False, False, padding_size)

        hbox = gtk.HBox()
        sensor_label = ful.make_label('Input: ', fg=ful.WHITE)
        sensor_value = ful.make_label('     ', fg=ful.WHITE)
        hbox.pack_start(sensor_label, False, False)
        hbox.pack_start(sensor_value, False, False)

        countdown_widget, self._countdown_label = ful.make_countdown_widget()
        self._countdown_label.set_text('%d' % timeout_per_subtest)
        hbox.pack_end(countdown_widget, False, False)

        vbox.pack_start(hbox, False, False)

        gobject.timeout_add(300, self.sensor_event, sensor_value)

        self._test_widget = vbox
        ful.run_test_widget(self.job, vbox,
            window_registration_callback=self.register_callbacks)

        failed_set = set(name for name, status in self._status_map.items()
                         if status is not ful.PASSED)
        if failed_set:
            raise error.TestFail('some subtests timed out (%s)' %
                                 ', '.join(failed_set))

        factory.log('%s run_once finished' % self.__class__)
