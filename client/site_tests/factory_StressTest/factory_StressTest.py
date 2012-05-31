# -*- coding: utf-8 -*-
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# Stress test on CPU, memory, and graphics. Also checks battery charging status.


import datetime
import functools
import gobject
import gtk
import logging
import os
from Queue import Queue
import re
import subprocess
import thread
import time
import traceback

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import ui
from autotest_lib.client.cros.factory import utils as factory_utils
from autotest_lib.client.cros.factory.event_log import EventLog


_MESSAGE_PROMPT = 'Stress Test'
_MESSAGE_STARTING = '... Starting Test ...'
_MESSAGE_TIMER = 'Started / 已執行時間: '
_MESSAGE_COUNTDOWN = 'ETA / 剩餘時間: '
_MESSAGE_LOADAVG = 'System Load: '

_MESSAGE_FAILED_LOADAVG = 'Failed to retrieve system load.'



SUBTESTS = factory_utils.Enum(['SAT', 'Load', 'Battery', 'Graphics'])


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


class BatteryInfo(object):
    BATTERY_INFO_PATH = '/sys/class/power_supply/BAT0'

    def get_value(self, key):
        try:
            with open(os.path.join(self.BATTERY_INFO_PATH, key), 'r') as f:
                return f.read().strip()
        except Exception:
            logging.warn('Unable to read battery value for %s.', key)
            return -1

    def get_status(self):
        return self.get_value('status')

    def get_charge_full(self):
        return int(self.get_value('charge_full_design'))

    def get_charge_now(self):
        return int(self.get_value('charge_now'))

    def get_voltage_now(self):
        return int(self.get_value('voltage_now'))


class factory_StressTest(test.test):
    version = 2

    def thread_SAT(self, seconds):
        if not self.job.run_test('hardware_SAT',
                                 drop_caches=True,
                                 seconds=seconds):
            raise error.TestError('Failed running hardware_SAT')

    def thread_Load(self, seconds):
        with open('/dev/null', 'w') as null:
            p = subprocess.Popen(('cat', '/dev/urandom'), stdout=null)
            if p.returncode is not None:
                raise error.TestError('Failed to start load test')
            time.sleep(seconds)
            p.kill()

    def thread_Battery(self, seconds):
        battery = BatteryInfo()
        charge_full = battery.get_charge_full()
        charge_begin = battery.get_charge_now()
        if (charge_begin < charge_full and
            battery.get_status() != 'Charging'):
            raise error.TestError('Battery not charging')
        time.sleep(seconds)
        charge_end = battery.get_charge_now()
        if charge_end < charge_full and charge_end < charge_begin:
            raise error.TestError('Battery not charged')

    def thread_Graphics(self, times):
        count = 0
        while count < times:
            time.sleep(2)
            count += 1
            result = self.job.run_test('graphics_GLMark2',
                                       subdir_tag=str(count))
            if not result:
                raise error.TestError('Failed running graphics_GLMark2')

    def _start_subtest(self, name, subtest, args):
        def target(args):
            start_time = time.time()
            try:
                self._event_log.Log('start_stress_subtest',
                                    name=name, args=args)
                subtest(args)
                self._event_log.Log('stop_stress_subtest',
                                    name=name, args=args,
                                    duration=(time.time() - start_time),
                                    status='PASSED')
            except Exception as e:
                self._error_queue.put(e)
                logging.exception('Subtest %s failed', name)
                self._event_log.Log('stop_stress_subtest',
                                    name=name, args=args,
                                    duration=(time.time() - start_time),
                                    status='FAILED',
                                    trace=traceback.format_exc())
            finally:
                self._complete.add(name)
        thread.start_new_thread(target, args)

    def timer_event(self, timer_label, countdown_label, load_label):
        if self._complete == SUBTESTS:
            with ui.gtk_lock:
                gtk.main_quit()
            return False

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

    def log_system_status(self, ectool, num_temp_sensor, battery):
        log_args = dict(
            fan_speed=ectool.get_fanspeed(),
            temperatures=[ectool.get_temperature(i)
                          for i in xrange(num_temp_sensor)],
            battery={'charge': battery.get_charge_now(),
                     'voltage': battery.get_voltage_now()})

        self._event_log.Log('sensor_measurement', **log_args)
        factory.log('Status at %s: %s' % (
                datetime.datetime.now().isoformat(),
                log_args))

    def monitor_event(self, ectool, num_temp_sensor, battery):
        self.log_system_status(ectool, num_temp_sensor, battery)
        return True

    def run_once(self,
                 sat_seconds=None,
                 sat_only=False,
                 runin_seconds=60,
                 graphics_test_times=1,
                 monitor_interval=None,
                 num_temp_sensor=1):
        factory.log('%s run_once' % self.__class__)
        # sat_seconds is deprecated, please use runin_seconds.
        # However, if sat_seconds is specified, the test list might want the
        # original sat behavior and not ready to run graphics/battery tests.
        if sat_seconds is not None:
            runin_seconds = sat_seconds
            sat_only = True

        self._complete = set()
        self._event_log = EventLog.ForAutoTest()
        self._error_queue = Queue()

        # Add 3 seconds leading time (for autotest / process to start).
        self._start_time = time.time() + 3
        self._end_time = self._start_time + runin_seconds + 1

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
            battery = BatteryInfo()
            self.log_system_status(ectool, num_temp_sensor, battery)
            gobject.timeout_add(1000 * monitor_interval,
                                self.monitor_event,
                                ectool,
                                num_temp_sensor,
                                battery)

        vbox.add(ui.make_label(_MESSAGE_PROMPT, font=ui.LABEL_LARGE_FONT))
        vbox.pack_start(timer_widget, padding=10)
        vbox.pack_start(load_label, padding=20)
        vbox.pack_start(countdown_widget, padding=10)

        if sat_only:
            self._start_subtest(SUBTESTS.SAT, self.thread_SAT, (runin_seconds,))
            self._complete |= SUBTESTS - set([SUBTESTS.SAT])
        else:
            if runin_seconds > 0:
                self._start_subtest(
                    SUBTESTS.SAT, self.thread_SAT, (runin_seconds,))
                self._start_subtest(
                    SUBTESTS.Load, self.thread_Load, (runin_seconds,))
                self._start_subtest(
                    SUBTESTS.Battery, self.thread_Battery,
                        (runin_seconds,))
            else:
                self._complete |= set(
                    [SUBTESTS.SAT, SUBTESTS.LOAD, SUBTESTS.Battery])
            if graphics_test_times > 0:
                self._start_subtest(SUBTESTS.Graphics,
                                    self.thread_Graphics,
                                    (graphics_test_times,))
            else:
                self._complete.add(SUBTESTS.GRAPHICS)
        ui.run_test_widget(self.job, vbox)

        if not self._error_queue.empty():
            # Raise only the first exception from worker threads.
            raise self._error_queue.get_nowait()

        factory.log('%s run_once finished' % self.__class__)
