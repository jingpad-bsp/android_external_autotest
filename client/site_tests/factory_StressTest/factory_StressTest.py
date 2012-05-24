# -*- coding: utf-8 -*-
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# Basic stress (CPU, memory, ...) factory test.


import datetime
import gobject
import gtk
import logging
import re
import thread
import time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import ui
from autotest_lib.client.cros.factory.event_log import EventLog


_MESSAGE_PROMPT = 'Basic Stress Test'
_MESSAGE_STARTING = '... Starting Test ...'
_MESSAGE_TIMER = 'Started / 已執行時間: '
_MESSAGE_COUNTDOWN = 'ETA / 剩餘時間: '
_MESSAGE_LOADAVG = 'System Load: '

_MESSAGE_FAILED_LOADAVG = 'Failed to retrieve system load.'

_SYSTEM_MONITOR_LOG_FORMAT = 'SYSTEM MONITOR [%s] %s: %d'


class ECControl(object):
    GET_FANSPEED_RE = 'Current fan RPM: ([0-9]*)'
    TEMP_SENSOR_RE = 'Reading temperature...([0-9]*)'

    def ec_command(self, cmd):
        full_cmd = 'ectool %s' % cmd
        result = utils.system_output(full_cmd)
        logging.debug('Command: %s', full_cmd)
        logging.debug('Result: %s', result)
        return result

    def get_fanspeed(self):
        try:
            response = self.ec_command('pwmgetfanrpm')
            return int(re.findall(self.GET_FANSPEED_RE, response)[0])
        except Exception:
            logging.warn('Unable to read fan speed.')
            return -1

    def get_temperature(self, idx):
        try:
            response = self.ec_command('temps %d' % idx)
            return int(re.findall(self.TEMP_SENSOR_RE, response)[0])
        except Exception:
            logging.warn('Unable to read temperature sensor %d.', idx)
            return -1


class factory_StressTest(test.test):
    version = 1

    def thread_SAT(self, seconds):
        try:
            result = self.job.run_test('hardware_SAT',
                                       drop_caches=True,
                                       seconds=seconds)
            if not result:
                raise error.TestError('Failed running hardware_SAT')
        finally:
            self._complete = True

    def timer_event(self, timer_label, countdown_label, load_label):
        if self._complete:
            with ui.gtk_lock:
                gtk.main_quit()
            return True

        now = time.time()
        if now <= self._start_time:
            # Still in leading time.
            load_label.set_text('%s %d' % (_MESSAGE_STARTING,
                                           self._start_time - now))
            return True

        timer = now - self._start_time
        countdown = self._end_time - now
        timer_label.set_text('%d:%02d' % (timer / 60, timer % 60))

        sign=' '
        if countdown < 0:
            countdown_label.modify_fg(gtk.STATE_NORMAL, ui.RED)
            countdown = abs(countdown)
            sign = '-'
        countdown_label.set_text(
                '%s%d:%02d' % (sign, countdown / 60, countdown % 60))
        try:
            with open('/proc/loadavg', 'r') as f:
                load_label.set_text(_MESSAGE_LOADAVG + f.read())
        except:
            load_label.set_text(_MESSAGE_FAILED_LOADAVG)
            load_label.modify_fg(gtk.STATE_NORMAL, ui.RED)
        return True

    def log_system_status(self, ectool, num_temp_sensor):
        fan_speed = ectool.get_fanspeed()
        temperatures = [ectool.get_temperature(i)
                        for i in xrange(num_temp_sensor)]

        self._event_log.Log('sensor_measurement',
                            fan_speed=fan_speed,
                            temperatures=temperatures)

        factory.log(_SYSTEM_MONITOR_LOG_FORMAT % (
            datetime.datetime.now().isoformat(),
            'Fan RPM', fan_speed))
        for i in xrange(num_temp_sensor):
            factory.log(_SYSTEM_MONITOR_LOG_FORMAT % (
                datetime.datetime.now().isoformat(),
                'Temp%d' % i,
                temperatures[i]))

    def monitor_event(self, ectool, num_temp_sensor):
        self.log_system_status(ectool, num_temp_sensor)
        return True

    def run_once(self,
                 sat_seconds=60,
                 monitor_interval=None,
                 num_temp_sensor=1):
        factory.log('%s run_once' % self.__class__)
        self._complete = False
        # Add 3 seconds leading time (for autotest / process to start).
        self._start_time = time.time() + 3
        self._end_time = self._start_time + sat_seconds + 1

        gtk.gdk.threads_init()
        vbox = gtk.VBox()
        timer_widget, timer_label = ui.make_countdown_widget(
                prompt=_MESSAGE_TIMER, value='', fg=ui.WHITE)
        countdown_widget, countdown_label = ui.make_countdown_widget(
                prompt=_MESSAGE_COUNTDOWN, value='')
        load_label = ui.make_label(_MESSAGE_STARTING, fg=ui.BLUE)
        gobject.timeout_add(1000, self.timer_event, timer_label,
                            countdown_label, load_label)
        if monitor_interval:
            ectool = ECControl()
            self._event_log = EventLog.ForAutoTest()
            self.log_system_status(ectool, num_temp_sensor)
            gobject.timeout_add(1000 * monitor_interval,
                                self.monitor_event,
                                ectool,
                                num_temp_sensor)
        vbox.add(ui.make_label(_MESSAGE_PROMPT, font=ui.LABEL_LARGE_FONT))
        vbox.pack_start(timer_widget, padding=10)
        vbox.pack_start(load_label, padding=20)
        vbox.pack_start(countdown_widget, padding=10)

        thread.start_new_thread(self.thread_SAT, (sat_seconds, ))
        ui.run_test_widget(self.job, vbox)

        factory.log('%s run_once finished' % self.__class__)
