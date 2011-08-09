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
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils

_LABEL_STATUS_SIZE = (140, 30)
_LABEL_RESPONSE_STR = ful.USER_PASS_FAIL_SELECT_STR + '\n'

_SUBTEST_LIST = ['Light sensor dark', 'Light sensor light']
_SUBTEST_CFG = {'Light sensor dark':{'min':4},
                'Light sensor light':{'max':1000}}

class iio_generic():
    '''
    Object to interface to ambient light sensor over iio.
    '''
    PARAMS = {'rd':'/sys/bus/iio/devices/device0/illuminance0_input',
              'init': '',
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
    version = 2

    def key_release_callback(self, widget, event):
        if event.keyval == ord('Q'):
            gtk.main_quit()
        return True

    def timer_event(self, countdown_label):
        time_remaining = max(0, self._deadline - time.time())
        if time_remaining is 0:
            factory.log('deadline reached')
            gtk.main_quit()

        countdown_label.set_text('%d' % time_remaining)
        countdown_label.queue_draw()
        gtk.main_iteration(False)
        return True

    def sensor_event(self, sensor_value):
        val = self._als.read('mean',samples=5, delay=0)

        passed = 0
        for name in _SUBTEST_LIST:
            cfg = _SUBTEST_CFG[name]
            if self._status_map[name] is ful.PASSED:
                # No need to recheck, we already passed.
                pass
            elif 'max' in cfg:
                if val > cfg['max']:
                    factory.log("Passed checking max %d > %d" % \
                                    (val, cfg['max']))
                    self._status_map[name] = ful.PASSED
                    self._status_label[name].queue_draw()
            elif 'min' in cfg:
                if val < cfg['min']:
                    factory.log("Passed checking min %d < %d" % \
                                    (val, cfg['min']))
                    self._status_map[name] = ful.PASSED
                    self._status_label[name].queue_draw()
            if self._status_map[name] is ful.PASSED:
                passed += 1

        if passed is len(_SUBTEST_LIST):
            factory.log('Passed all sensor tests')
            gtk.main_quit()

        sensor_value.set_text('%d' % val)
        sensor_value.queue_draw()
        gtk.main_iteration(False)
        return True


    def label_status_expose(self, widget, event, name):
        status = self._status_map[name]
        widget.set_text(status)
        widget.modify_fg(gtk.STATE_NORMAL, ful.LABEL_COLORS[status])
        return False


    def make_subtest_label_box(self, name):
        eb = gtk.EventBox()
        eb.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        label_status = ful.make_label(ful.UNTESTED, size=_LABEL_STATUS_SIZE,
                                      alignment=(0, 0.5),
                                      fg=ful.LABEL_COLORS[ful.UNTESTED])
        label_status.connect('expose_event', self.label_status_expose, name)
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

        self._als = iio_generic()
        self._deadline = time.time() + timeout

        self._subtest_queue = [x for x in reversed(_SUBTEST_LIST)]
        self._status_map = dict((n, ful.ACTIVE) for n in _SUBTEST_LIST)

        vbox = gtk.VBox()
        prompt_label = ful.make_label(
            'Cover Sensor with Finger (Input < %s)\n' % lux_min +
            '请遮蔽光传感器\n\n' +
            'Shine flashlight at Sensor (Input > %s)\n' % lux_max +
            '请以灯光照射光传感器\n',
            fg=ful.WHITE)
        vbox.pack_start(prompt_label, False, False)

        hbox = gtk.HBox()
        sensor_label = ful.make_label('Input: ', fg=ful.WHITE)
        sensor_value = ful.make_label('     ', fg=ful.WHITE)
        hbox.pack_start(sensor_label, False, False)
        hbox.pack_start(sensor_value, False, False)
        vbox.pack_start(hbox, False, False)

        self._status_label = {}
        for name in _SUBTEST_LIST:
            label_box = self.make_subtest_label_box(name)
            vbox.pack_start(label_box, False, False)
            self._status_label[name] = label_box
            cfg = _SUBTEST_CFG[name]
            # change defaults per factory setup
            if 'max' in cfg and lux_max is not None:
                cfg['max'] = lux_max
            if 'min' in cfg and lux_min is not None:
                cfg['min'] = lux_min

        countdown_widget, countdown_label = ful.make_countdown_widget()
        vbox.pack_start(countdown_widget, False, False)
        gobject.timeout_add(1000, self.timer_event, countdown_label)
        gobject.timeout_add(300, self.sensor_event, sensor_value)

        self._test_widget = vbox
        ful.run_test_widget(self.job, vbox,
            window_registration_callback=self.register_callbacks)

        failed_set = set(name for name, status in self._status_map.items()
                         if status is not ful.PASSED)
        if failed_set:
            raise error.TestFail('some subtests failed (%s)' %
                                 ', '.join(failed_set))

        factory.log('%s run_once finished' % self.__class__)
