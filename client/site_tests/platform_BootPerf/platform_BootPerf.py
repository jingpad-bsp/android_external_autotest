# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import re
import utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class platform_BootPerf(test.test):
    version = 1


    def __parse_uptime(self, filename):
        vals = []
        try:
            data = file(filename).read()
            vals = re.split(r' +', data.strip())
        except IOError:
            raise error.TestFail('Test is unable to read uptime file "%s"' %
                                 filename)
        return float(vals[0])


    def __parse_disk_login_prompt_ready(self, results):
        filename = '/tmp/disk-login-prompt-ready'
        vals = []
        try:
            data = file(filename).read()
            vals = re.split(r' +', data.strip())
        except IOError:
            raise error.TestFail('Test is unable to read "%s"' % filename)
        results['sectors_read_kernel_to_login'] = float(vals[2])


    def __parse_syslog_for_firmware_time(self, results):
        file_handle = None
        logfile = '/var/log/messages'
        try:
            file_handle = open(logfile, 'r')
        except:
            raise error.TestFail('Test is unable to read "%s"' % logfile)
        mhz = 0
        ticks = 0
        startups_found = 0
        last_reboot = None
        firmware_time = None
        seconds_firmware_boot = 0
        datetime_re = r'^(\d{4})-(\d{2})-(\d{2})[A-Z]' + \
                      r'(\d{2}):(\d{2}):(\d{2})\.(\d{6})'
        last_reboot_re = re.compile(datetime_re + \
                                    r'.*klog main process.*killed by TERM')
        startup_re = re.compile(r'000\] Linux version \d')
        mhz_re = re.compile(r'Detected (\d+\.\d+) MHz processor.')
        initial_tsc_re = re.compile(datetime_re + r'.*Initial TSC value: (\d+)')
        for line in file_handle.readlines():
            if startup_re.search(line) is not None:
                mhz = 0
                ticks = 0
                firmware_time = None
                startups_found += 1
            match = last_reboot_re.search(line)
            if match is not None:
                datetime_args = tuple([int(x) for x in match.groups()[:7]])
                last_reboot = datetime.datetime(*datetime_args)
            match = mhz_re.search(line)
            if match is not None:
                mhz = float(match.group(1))
            match = initial_tsc_re.search(line)
            if match is not None:
                datetime_args = tuple([int(x) for x in match.groups()[:7]])
                firmware_time = datetime.datetime(*datetime_args)
                ticks = int(match.group(8))
                logging.info('Found initial TSC: %d' % ticks)
        file_handle.close()
        if mhz > 0 and startups_found > 0 and ticks > 0:
            seconds_firmware_boot = float(ticks) / mhz / 1000000
            results['seconds_firmware_boot'] = seconds_firmware_boot
        if last_reboot != None and firmware_time != None:
            delta = firmware_time - last_reboot
            # Hopefully it won't take days... :) But just so we can
            # see if this test is producing nonsense, we include it.
            reboot_time = (float(delta.days) * 86400.0 +
                           float(delta.seconds) +
                           float(delta.microseconds) /
                           1000000.0)
            results['seconds_reboot_time'] = reboot_time
            results['seconds_shutdown_time'] = \
                reboot_time - seconds_firmware_boot
        results['reboots_in_syslog'] = startups_found
        results['mhz_primary_cpu'] = mhz


    def run_once(self, max_startup_time=6.0, max_shutdown_time=1.0):
        # Parse key metric files and generate key/value pairs
        results = {}

        uptime_files = [
            ('seconds_kernel_to_startup', '/tmp/uptime-pre-startup'),
            ('seconds_kernel_to_startup_done', '/tmp/uptime-post-startup'),
            ('seconds_kernel_to_login', '/tmp/uptime-login-prompt-ready')]

        for resultname, filename in uptime_files:
            results[resultname] = self.__parse_uptime(filename)

        self.__parse_disk_login_prompt_ready(results)
        self.__parse_syslog_for_firmware_time(results)

        if ('seconds_firmware_boot' in results and
            'seconds_kernel_to_login' in results):
            results['seconds_power_on_to_login'] = \
                results['seconds_firmware_boot'] + \
                results['seconds_kernel_to_login']

        self.write_perf_keyval(results)

        # Fail the test if it's unable to determine what it's trying
        # to determine, but log all the things we were unable to
        # determine before failing.
        errors = 0
        if 'seconds_firmware_boot' not in results:
            errors += 1
            logging.error('Unable to determine firmware boot time.')
        if 'seconds_power_on_to_login' not in results:
            errors += 1
            logging.error('Unable to determine power on to login time.')
        if 'seconds_shutdown_time' not in results:
            errors += 1
            logging.error('Unable to determine shutdown time.')

        if errors > 0:
            raise error.TestFail('Unable to determine boot performance.')

        # Check to see if we met our test criteria, and log them all
        # before failing the test.
        errors = 0
        if ('seconds_power_on_to_login' in results and
            results['seconds_power_on_to_login'] > max_startup_time):
            errors += 1
            logging.error('Startup time was %2.2fs, '
                          'exceeding %2.2fs criterion by '
                          '%2.2f seconds' %
                          (results['seconds_power_on_to_login'],
                           max_startup_time,
                           results['seconds_power_on_to_login'] -
                           max_startup_time))

        if ('seconds_shutdown_time' in results and
            results['seconds_shutdown_time'] > max_shutdown_time):
            errors += 1
            logging.error('Shutdown time was %2.2fs, exceeding %2.2fs '
                          'criterion by %2.2f seconds' %
                          (results['seconds_shutdown_time'],
                           max_shutdown_time,
                           results['seconds_shutdown_time'] -
                           max_shutdown_time))

        if errors > 0:
            raise error.TestFail('Boot performance didn\'t meet criteria')
