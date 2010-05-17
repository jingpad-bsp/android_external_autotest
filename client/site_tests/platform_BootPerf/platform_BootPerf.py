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


    def __parse_firmware_boot_time(self, results):
        data = None
        try:
            # If the firmware boot time is not available, the file
            # will not exists.
            data = utils.read_one_line('/tmp/firmware-boot-time')
        except IOError:
            return
        results['seconds_firmware_boot'] = float(data)


    # Find the reboot/shutdown time if the last boot was a reboot.
    def __parse_syslog(self, results, last_boot_was_reboot):
        file_handle = None
        logfile = '/var/log/messages'
        try:
            file_handle = open(logfile, 'r')
        except:
            raise error.TestFail('Test is unable to read "%s"' % logfile)
        mhz = 0
        startups_found = 0
        last_shutdown_time = None
        kernel_start_time = None
        datetime_re = r'(\d{4})-(\d{2})-(\d{2})[A-Z]' + \
                      r'(\d{2}):(\d{2}):(\d{2})\.(\d{6})'
        last_shutdown_re = re.compile(
            datetime_re + r'.*(klog|tty2) main process.*killed by TERM')
        startup_re = re.compile(datetime_re + r'.*000\] Linux version \d')
        mhz_re = re.compile(r'Detected (\d+\.\d+) MHz processor.')
        for line in file_handle.readlines():
            match = startup_re.match(line)
            if match is not None:
                mhz = 0
                datetime_args = tuple([int(x) for x in match.groups()[:7]])
                kernel_start_time = datetime.datetime(*datetime_args)
                startups_found += 1
            match = last_shutdown_re.match(line)
            if match is not None:
                datetime_args = tuple([int(x) for x in match.groups()[:7]])
                last_shutdown_time = datetime.datetime(*datetime_args)
            match = mhz_re.search(line)
            if match is not None:
                mhz = float(match.group(1))
        file_handle.close()
        if (last_shutdown_time != None and last_boot_was_reboot and
            kernel_start_time != None):
            logging.info('Kernel start time: %s, last shutdown time: %s' %
                         (kernel_start_time, last_shutdown_time))
            delta = kernel_start_time - last_shutdown_time
            # There is no guarantee that we will have gotten a shutdown
            # log message/time.  It's possible to not get any kill messages
            # logged to syslog before rsyslogd itself is killed.  If
            # that occurs, this reboot time will be completely wrong.
            reboot_time = (float(delta.days) * 86400.0 +
                           float(delta.seconds) +
                           float(delta.microseconds) /
                           1000000.0)
            results['seconds_reboot_time'] = reboot_time
            results['seconds_shutdown_time'] = \
                reboot_time - results.get('seconds_firmware_boot', 0.0)
        results['reboots_in_syslog'] = startups_found
        results['mhz_primary_cpu'] = mhz


    def run_once(self, last_boot_was_reboot=False):
        # Parse key metric files and generate key/value pairs
        results = {}

        uptime_files = [
            ('seconds_kernel_to_startup', '/tmp/uptime-pre-startup'),
            ('seconds_kernel_to_startup_done', '/tmp/uptime-post-startup'),
            ('seconds_kernel_to_login', '/tmp/uptime-login-prompt-ready')]

        for resultname, filename in uptime_files:
            results[resultname] = self.__parse_uptime(filename)

        self.__parse_firmware_boot_time(results)
        self.__parse_disk_login_prompt_ready(results)
        self.__parse_syslog(results, last_boot_was_reboot)

        if ('seconds_firmware_boot' in results and
            'seconds_kernel_to_login' in results):
            results['seconds_power_on_to_login'] = \
                results['seconds_firmware_boot'] + \
                results['seconds_kernel_to_login']

        self.write_perf_keyval(results)
