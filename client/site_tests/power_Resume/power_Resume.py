# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import commands, logging, random, re, time
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import rtc, sys_power

START_SUSPEND_MESSAGES = [ 'Freezing user space' ]
END_SUSPEND_MESSAGES = [ 'Back to C!', 'Resume caused by' ]
END_RESUME_MESSAGES = [ 'Restarting tasks' ]

class power_Resume(test.test):
    version = 1
    preserve_srcdir = True


    def _get_last_msg(self, msg):
        cmd = "grep -a '%s' /var/log/messages | tail -n 1" % msg
        # The order in which processes are un-frozen is indeterminate
        # and therfore this test may get resumed before the system has gotten
        # a chance to finalize writes to logfile. Sleep a bit to take care of
        # this race.
        count = 0
        data = commands.getoutput(cmd)
        while len(data) == 0 and count < 5:
            count +=1
            time.sleep(1)
            data = commands.getoutput(cmd)

        if count == 5:
            raise error.TestError("Failed to find log message: " + msg)

        return data

    def _get_last_msg_time(self, msg):
        data = self._get_last_msg(msg)
        match = re.search(r' \[\s*([0-9.]+)\] ', data)
        if match is None:
            raise error.TestError('Failed to find timestamp for log message: '
                                  + msg)

        msg_time = float(match.group(1))
        logging.debug("Last message '%s' time = %f" % (msg, msg_time))
        return msg_time

    def _get_last_msg_time_multiple(self, msgs):
        time = -1
        for msg in msgs:
            try:
                time = self._get_last_msg_time(msg)
                break
            except error.TestError as e:
                logging.info("%s, trying next message" % str(e))

        return time

    def _get_start_suspend_time(self):
        time = self._get_last_msg_time_multiple(START_SUSPEND_MESSAGES)
        if time == -1:
            raise error.TestError("Could not find start suspend time message.")

        return time

    def _get_end_cpu_resume_time(self):
        # systems with only one logical CPU won't have this message, return -1
        try:
            time = self._get_last_msg_time('CPU[0-9]\+ is up')
        except error.TestError:
            time = -1

        return time

    def _get_end_suspend_time(self):
        time = self._get_last_msg_time_multiple(END_SUSPEND_MESSAGES)
        if time == -1:
            raise error.TestError("Could not find end suspend time message.")

        return time

    def _get_end_resume_time(self):
        time = self._get_last_msg_time_multiple(END_RESUME_MESSAGES)
        if time == -1:
            raise error.TestError("Could not find end resume time message.")

        return time

    def _get_device_resume_time(self):
        data = self._get_last_msg("PM: resume of devices complete after")
        match = re.search(r'PM: resume of devices complete after ([0-9.]+)',
                          data)
        if match is None:
            raise error.TestError('Failed to find device resume time on line: '
                                  + data)
        # convert from msec to sec
        return float(match.group(1)) / 1000

    def _get_hwclock_seconds(self):
        """
        Read the hwclock resume time saved off by powerd_resume
        """
        count = 0
        while count < 5:
            hwclock_output = utils.read_file('/tmp/hwclock-on-resume')
            logging.debug('hwclock_output: ' + hwclock_output)
            match = re.search(
                    r'= ([0-9]+) seconds since .+ (-?[0-9.]+) seconds$',
                    hwclock_output, re.DOTALL)
            if match:
                seconds = int(match.group(1)) + float(match.group(2))
                logging.debug('hwclock seconds = %f' % seconds)
                return seconds

            # /tmp/hwclock-on-resume file doesn't contain valid data. Retry
            count += 1
            time.sleep(1)

        raise ValueError('Unable to read the hardware clock -- ' +
                         hwclock_output)


    def run_once(self):
        # Some idle time before initiating suspend-to-ram
        idle_time = random.randint(1, 10)
        time.sleep(idle_time)

        # Safe enough number, can tweek if necessary
        time_to_sleep = 10

        # Set the alarm
        alarm_time = rtc.get_seconds() + time_to_sleep
        logging.debug('alarm_time = %d', alarm_time)
        rtc.set_wake_alarm(alarm_time)

        # Suspend the system to RAM
        sys_power.suspend_to_ram()

        # Get suspend and resume times from /var/log/messages
        start_suspend_time = self._get_start_suspend_time()
        end_suspend_time = self._get_end_suspend_time()
        end_resume_time = self._get_end_resume_time()
        end_cpu_resume_time = self._get_end_cpu_resume_time()
        kernel_device_resume_time = self._get_device_resume_time()

        # Calculate the suspend/resume times
        total_resume_time = self._get_hwclock_seconds() - alarm_time
        suspend_time = end_suspend_time - start_suspend_time
        kernel_resume_time = end_resume_time - end_suspend_time

        kernel_cpu_resume_time = 0
        if end_cpu_resume_time > 0:
            kernel_cpu_resume_time = end_cpu_resume_time - end_suspend_time

        firmware_resume_time = total_resume_time - kernel_resume_time

        # Prepare the results
        results = {}
        results['seconds_system_suspend'] = suspend_time
        results['seconds_system_resume'] = total_resume_time
        results['seconds_system_resume_firmware'] = firmware_resume_time
        results['seconds_system_resume_kernel'] = kernel_resume_time
        results['seconds_system_resume_kernel_cpu'] = kernel_cpu_resume_time
        results['seconds_system_resume_kernel_dev'] = kernel_device_resume_time
        self.write_perf_keyval(results)
