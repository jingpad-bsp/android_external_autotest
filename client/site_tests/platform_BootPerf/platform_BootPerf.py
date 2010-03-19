# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re
import subprocess
import time
import utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class platform_BootPerf(test.test):
    version = 1


    def __parse_uptime_login_prompt_ready(self, results):
        data = file('/tmp/uptime-login-prompt-ready').read()
        vals = re.split(r' +', data.strip())
        results['seconds_kernel_to_login'] = float(vals[0])


    def __parse_disk_login_prompt_ready(self, results):
        data = file('/tmp/disk-login-prompt-ready').read()
        vals = re.split(r' +', data.strip())
        results['sectors_read_kernel_to_login'] = float(vals[2])


    def __parse_syslog_for_firmware_time(self, results):
        f = open('/var/log/messages', 'r')
        mhz = 0
        ticks = 0
        reboots_found = 0
        reboot_re = re.compile('000\] Linux version \d')
        mhz_re = re.compile('Detected (\d+\.\d+) MHz processor.')
        initial_tsc_re = re.compile('Initial TSC value: (\d+)')
        for line in f.readlines():
            if reboot_re.search(line) is not None:
                mhz = 0
                ticks = 0
                reboots_found += 1
            match = mhz_re.search(line)
            if match is not None:
                mhz = float(match.group(1))
            match = initial_tsc_re.search(line)
            if match is not None:
                ticks = int(match.group(1))
                logging.info('Found initial TSC: %d' % ticks)
        f.close()
        if mhz > 0 and reboots_found > 0 and ticks > 0:
            seconds_firmware_boot = float(ticks) / mhz / 1000000
            results['seconds_firmware_boot'] = seconds_firmware_boot
        results['reboots_in_syslog'] = reboots_found
        results['mhz_primary_cpu'] = mhz


    def run_once(self):
        # Parse key metric files and generate key/value pairs
        results = {}
        self.__parse_uptime_login_prompt_ready(results)
        self.__parse_disk_login_prompt_ready(results)
        self.__parse_syslog_for_firmware_time(results)

        if ('seconds_firmware_boot' in results and
            'seconds_kernel_to_login' in results):
            results['seconds_power_on_to_login'] = (
                results['seconds_firmware_boot'] +
                results['seconds_kernel_to_login'])

        self.write_perf_keyval(results)
