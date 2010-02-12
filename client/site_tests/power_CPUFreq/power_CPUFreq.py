# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob, logging, os
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils

class power_CPUFreq(test.test):
    version = 1

    def run_once(self):
        cpufreq_path = '/sys/devices/system/cpu/cpu*/cpufreq'

        dirs  = glob.glob(cpufreq_path)
        if not dirs:
            raise error.TestFail('cpufreq not supported')

        for dir in dirs:
            cpu = cpufreq(dir)

            if 'userspace' not in cpu.get_available_governors():
                raise error.TestError('userspace governor not supported')

            available_frequencies = cpu.get_available_frequencies()
            if len(available_frequencies) == 1:
                raise error.TestFail('Not enough frequencies supported!')

            # save cpufreq state so that it can be restored at the end
            # of the test
            cpu.save_state()

            # set cpufreq governor to userspace
            cpu.set_governor('userspace')

            # cycle through all available frequencies
            for freq in available_frequencies:
                cpu.set_frequency(freq)
                if freq != cpu.get_current_frequency():
                    cpu.restore_state()
                    raise error.TestFail('Unable to set frequency')

            # restore cpufreq state
            cpu.restore_state()


class cpufreq(object):
    def __init__(self, path):
        self.__base_path = path
        self.__save_files_list = ['scaling_max_freq', 'scaling_min_freq',
                                  'scaling_governor']


    def __write_file(self, file_name, data):
        path = os.path.join(self.__base_path, file_name)
        utils.open_write_close(path, data)


    def __read_file(self, file_name):
        path = os.path.join(self.__base_path, file_name)
        f = open(path, 'r')
        data = f.read()
        f.close()
        return data


    def save_state(self):
        logging.info('saving state:')
        for file in self.__save_files_list:
            data = self.__read_file(file)
            setattr(self, file, data)
            logging.info(file + ': '  + data)


    def restore_state(self):
        logging.info('restoring state:')
        for file in self.__save_files_list:
            data = getattr(self, file)
            logging.info(file + ': '  + data)
            self.__write_file(file, data)


    def get_available_governors(self):
        governors = self.__read_file('scaling_available_governors')
        logging.info('available governors: %s' % governors)
        return governors.split()


    def get_current_governor(self):
        governor = self.__read_file('scaling_governor')
        logging.info('current governor: %s' % governor)
        return governor.split()[0]


    def set_governor(self, governor):
        logging.info('setting governor to %s' % governor)
        self.__write_file('scaling_governor', governor)


    def get_available_frequencies(self):
        frequencies = self.__read_file('scaling_available_frequencies')
        logging.info('available frequencies: %s' % frequencies)
        return [int(i) for i in frequencies.split()]


    def get_current_frequency(self):
        freq = int(self.__read_file('scaling_cur_freq'))
        logging.info('current frequency: %s' % freq)
        return freq


    def set_frequency(self, frequency):
        logging.info('setting frequency to %d' % frequency)
        if frequency >= self.get_current_frequency():
            file_list = ['scaling_max_freq', 'scaling_min_freq',
                         'scaling_setspeed']
        else:
            file_list = ['scaling_min_freq', 'scaling_max_freq',
                         'scaling_setspeed']

        for file in file_list:
            self.__write_file(file, str(frequency))
