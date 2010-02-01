# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import commands, logging, os, re, time, utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class metrics_Resume(test.test):
    version = 1
    preserve_srcdir = True


    def __get_last_msg_time(self, msg):
        data = commands.getoutput(
            "cat /var/log/messages | grep '%s' | tail -n 1" % msg)
        match = re.search(r' \[\s*([0-9.]+)\] ', data)
        if match is None:
            raise error.TestError('Failed to find log message: ' + msg)

        msg_time = float(match.group(1))
        logging.debug("Last message '%s' time = %f" % (msg, msg_time))
        return msg_time


    def __get_start_suspend_time(self):
        return self.__get_last_msg_time('Freezing user space')


    def __get_end_suspend_time(self):
        return self.__get_last_msg_time('CPU[0-9] is down')


    def get_hwclock_seconds(self, utc=True):
        """
        Return the hardware clock in seconds as a floating point value.
        Use Coordinated Universal Time if utc is True, local time otherwise.
        Raise a ValueError if unable to read the hardware clock.
        """
        cmd = '/sbin/hwclock --debug'
        if utc:
            cmd += ' --utc'
        hwclock_output = utils.system_output(cmd, ignore_status=True)
        match = re.search(r'= ([0-9]+) seconds since .+ (-?[0-9.]+) seconds$',
                          hwclock_output, re.DOTALL)
        if match:
            seconds = int(match.group(1)) + float(match.group(2))
            logging.debug('hwclock seconds = %f' % seconds)
            return seconds

        raise ValueError('Unable to read the hardware clock -- ' +
                         hwclock_output)


    def run_once(self, itersleep=None):
        if itersleep is not None:
            time.sleep(itersleep)

        # Safe enough number, can tweek if necessary
        time_to_sleep = 10

        # Set the alarm
        alarm_time = int(self.get_hwclock_seconds()) + time_to_sleep
        logging.debug('alarm_time = %d' % alarm_time)
        set_wake_command = 'echo ' + str(alarm_time) + \
                           ' > /sys/class/rtc/rtc0/wakealarm'
        if commands.getstatusoutput(set_wake_command)[0] != 0:
            raise error.TestError('Failure to set wake alarm')

        # Suspend the system to RAM
        sleep_command = "echo mem > /sys/power/state"
        (status, output) = commands.getstatusoutput(sleep_command)
        if status != 0:
            raise error.TestError('Failure to suspend to RAM')

        # Calculate the suspend/resume times
        resume_time = self.get_hwclock_seconds() - alarm_time
        suspend_time = \
            self.__get_end_suspend_time() - self.__get_start_suspend_time()

        # Prepare the results
        results = {}
        results['seconds_system_suspend'] = suspend_time
        results['seconds_system_resume'] = resume_time
        self.write_perf_keyval(results)
