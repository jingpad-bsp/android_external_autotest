# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import fnmatch
import logging
import os
import re
import shutil
import utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class platform_BootPerf(test.test):
    version = 2


    def __copy_timestamp_files(self):
        tmpdir = '/tmp'
        for fname in os.listdir(tmpdir):
          if (not fnmatch.fnmatch(fname, 'uptime-*') and
                  not fnmatch.fnmatch(fname, 'disk-*')):
              continue
          shutil.copy(os.path.join(tmpdir, fname), self.resultsdir)
        try:
          shutil.copy('/tmp/firmware-boot-time', self.resultsdir)
        except:
          pass


    def __parse_uptime(self, filename):
        vals = []
        try:
            data = file(filename).read()
            vals = re.split(r' +', data.strip())
        except IOError:
            raise error.TestFail('Test is unable to read uptime file "%s"' %
                                 filename)
        return float(vals[0])


    def __parse_diskstat(self, filename):
        vals = []
        try:
            data = file(filename).read()
            vals = re.split(r' +', data.strip())
        except IOError:
            raise error.TestFail('Test is unable to read "%s"' % filename)
        return float(vals[2])


    def __parse_firmware_boot_time(self, results):
        data = None
        try:
            # If the firmware boot time is not available, the file
            # will not exist.
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
        self.__copy_timestamp_files()

        # Parse key metric files and generate key/value pairs
        results = {}

        uptime_files = [
            # N.B.  Keyval attribute names go into a database that
            # truncates after 30 characters.
            # ----+----1----+----2----+----3
            ('seconds_kernel_to_startup',      '/tmp/uptime-pre-startup'),
            ('seconds_kernel_to_startup_done', '/tmp/uptime-post-startup'),
            ('seconds_kernel_to_x_started',    '/tmp/uptime-x-started'),
            ('seconds_kernel_to_chrome_exec',  '/tmp/uptime-chrome-exec'),
            ('seconds_kernel_to_chrome_main',  '/tmp/uptime-chrome-main'),
            ('seconds_kernel_to_login',        '/tmp/uptime-boot-complete')
        ]

        for resultname, filename in uptime_files:
            results[resultname] = self.__parse_uptime(filename)

        # Not all 'uptime-network-*-ready' files necessarily exist;
        # probably there's only one.  We go through a list of
        # possibilities and pick the first one we find.  We're not
        # looking for 3G here, so we're not guaranteed to find any
        # file.
        network_time_files = [
            '/tmp/uptime-network-wifi-ready',
            '/tmp/uptime-network-ethernet-ready' ]

        for filename in network_time_files:
            try:
                network_time = self.__parse_uptime(filename)
                results['seconds_kernel_to_network'] = network_time
                break
            except error.TestFail:
                pass

        diskstat_files = [
            # N.B. 30 character name limit -- see above.
            # ----+----1----+----2----+----3
            ('rdbytes_kernel_to_startup',      '/tmp/disk-pre-startup'),
            ('rdbytes_kernel_to_startup_done', '/tmp/disk-post-startup'),
            ('rdbytes_kernel_to_x_started',    '/tmp/disk-x-started'),
            ('rdbytes_kernel_to_chrome_exec',  '/tmp/disk-chrome-exec'),
            ('rdbytes_kernel_to_chrome_main',  '/tmp/disk-chrome-main'),
            ('rdbytes_kernel_to_login',        '/tmp/disk-boot-complete')
        ]

        # Disk statistics are reported in units of 512 byte sectors;
        # we want the keyvals to report bytes so that downstream
        # consumers don't have to ask "How big is a sector?".
        for resultname, filename in diskstat_files:
            try:
                results[resultname] = 512 * self.__parse_diskstat(filename)
            except:
                pass

        self.__parse_firmware_boot_time(results)
        self.__parse_syslog(results, last_boot_was_reboot)

        if ('seconds_firmware_boot' in results and
            'seconds_kernel_to_login' in results):
            results['seconds_power_on_to_login'] = \
                results['seconds_firmware_boot'] + \
                results['seconds_kernel_to_login']

        self.write_perf_keyval(results)
