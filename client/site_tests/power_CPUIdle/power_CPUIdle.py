# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob, logging, os, time
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


class power_CPUIdle(test.test):
    version = 1

    def run_once(self, sleep_time=5):
        all_cpus = cpus()

        idle_time_at_start = all_cpus.idle_time()
        logging.info('idle_time_at_start: %d' % idle_time_at_start)

        # sleep for some time to allow the CPUs to drop into idle states
        time.sleep(sleep_time)

        idle_time_at_end = all_cpus.idle_time()
        logging.info('idle_time_at_end: %d' % idle_time_at_end)

        idle_time_delta_ms = (idle_time_at_end - idle_time_at_start) / 1000
        logging.info('idle time delta (ms): %d' % idle_time_delta_ms)

        if idle_time_at_end == idle_time_at_start:
            raise error.TestFail('No Idle cycles')



class cpus(object):
    def __init__(self):
        self.__base_path = '/sys/devices/system/cpu/cpu*/cpuidle'
        self.__cpus = []

        dirs = glob.glob(self.__base_path)
        if not dirs:
            raise error.TestError('cpuidle not supported')

        for dir in dirs:
            cpu = cpuidle(dir)
            self.__cpus.append(cpu)


    def idle_time(self):
        total_idle_time = 0
        for cpu in self.__cpus:
            total_idle_time += cpu.idle_time()
        return total_idle_time



class cpuidle(object):
    def __init__(self, path):
        self.__base_path = path
        self.__states = []

        dirs = glob.glob(os.path.join(self.__base_path, 'state*'))
        if not dirs:
            raise error.TestError('cpuidle states missing')

        for dir in dirs:
            state = cpuidle_state(dir)
            self.__states.append(state)


    def idle_time(self):
        total_idle_time = 0
        for state in self.__states:
            total_idle_time += state.idle_time()

        return total_idle_time



class cpuidle_state(object):
    def __init__(self, path):
        self.__base_path = path
        self.__name = self.__read_file('name').split()[0]


    def __read_file(self, file_name):
        path = os.path.join(self.__base_path, file_name)
        f = open(path, 'r')
        data = f.read()
        f.close()
        return data


    def idle_time(self):
        time = int(self.__read_file('time'))
        logging.info('idle_time(%s): %s' % (self.__name, time))
        return time
