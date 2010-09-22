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

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test
from autotest_lib.client.bin import factory_error as error
from autotest_lib.client.common_lib import utils

_LABEL_STATUS_SIZE = (140, 30)
_LABEL_RESPONSE_STR = ful.USER_PASS_FAIL_SELECT_STR + '\n'

_SUBTEST_LIST = ['Light sensor dark', 'Light sensor light']
_SUBTEST_CFG = {'Light sensor dark':{'min':4},
                'Light sensor light':{'max':1000}}

class tsl2563():
    '''
    Object to interface to ambient light sensor tsl2563
    '''
    PARAMS = {'rd':'/sys/class/iio/device0/lux',
              'init': \
                  'echo tsl2563 0x29 > /sys/class/i2c-adapter/i2c-2/new_device',
              'min':0,
              'max':math.pow(2,16),
              # in seconds
              'mindelay':0.178,
              }

    def __init__(self):
        self.buf = []
        self.ambient = None

        if not os.path.isfile(self.PARAMS['rd']):
            self.cfg()

        self.ambient = self.read('mean',delay=0,samples=10)
        factory.log('ambient light sensor = %d' % self.ambient)

    def cfg(self):
        cmd = self.PARAMS['init']
        utils.system(cmd)
        time.sleep(1)
        if not os.path.isfile(self.PARAMS['rd']):
            raise error.TestError(cmd + 'did not create ' + self.PARAMS['rd'])
        val = self.read('first',samples=1)
        if val <= self.PARAMS['min'] or val >= self.PARAMS['max']:
            raise error.TestError("Failed initial read\n")


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
    version = 1

    def key_release_callback(self, widget, event):
        if event.keyval == ord('Q'):
            gtk.main_quit()
        return True

    def timer_event(self, countdown_label):
        val = self._als.read('mean',samples=5, delay=0)
        #factory.log("avg_val = %d" % val)

        passed = 0
        for name in _SUBTEST_LIST:
            cfg = _SUBTEST_CFG[name]
            if 'max' in cfg:
                if val > cfg['max']:
                    factory.log("Passed checking max %d > %d" % \
                                    (val, cfg['max']))
                    self._status_map[name] = ful.PASSED
            elif 'min' in cfg:
                if val < cfg['min']:
                    factory.log("Passed checking min %d < %d" % \
                                    (val, cfg['min']))
                    self._status_map[name] = ful.PASSED
            if self._status_map[name] is ful.PASSED:
                passed += 1

        if passed is len(_SUBTEST_LIST):
            factory.log('Passed all sensor tests')
            gtk.main_quit()

        time_remaining = max(0, self._deadline - time.time())
        if time_remaining is 0:
            factory.log('deadline reached')
            gtk.main_quit()

        countdown_label.set_text('%d' % time_remaining)
        countdown_label.queue_draw()
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
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gtk.gdk.KEY_RELEASE_MASK)

    def run_once(self,
                 lux_min=None,
                 lux_max=None,
                 timeout=60):

        factory.log('%s run_once' % self.__class__)

        self._als = tsl2563()
        self._deadline = time.time() + timeout

        self._subtest_queue = [x for x in reversed(_SUBTEST_LIST)]
        self._status_map = dict((n, ful.ACTIVE) for n in _SUBTEST_LIST)

        vbox = gtk.VBox()
        prompt_label = ful.make_label(
            'Cover Sensor with Finger\n' + '请遮蔽光传感器\n\n' +
            'Shine flashlight at Sensor\n' + '请以灯光照射光传感器\n\n',
            fg=ful.WHITE)
        vbox.pack_start(prompt_label, False, False)

        for name in _SUBTEST_LIST:
            label_box = self.make_subtest_label_box(name)
            vbox.pack_start(label_box, False, False)
            cfg = _SUBTEST_CFG[name]
            # change defaults per factory setup
            if 'max' in cfg and lux_max is not None:
                cfg['max'] = lux_max
            if 'min' in cfg and lux_min is not None:
                cfg['min'] = lux_min

        countdown_widget, countdown_label = ful.make_countdown_widget()
        vbox.pack_start(countdown_widget, False, False)
        gobject.timeout_add(200, self.timer_event, countdown_label)

        self._test_widget = vbox
        ful.run_test_widget(self.job, vbox,
            window_registration_callback=self.register_callbacks)

        failed_set = set(name for name, status in self._status_map.items()
                         if status is not ful.PASSED)
        if failed_set:
            raise error.TestFail('some subtests failed (%s)' %
                                 ', '.join(failed_set))

        factory.log('%s run_once finished' % self.__class__)
