# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import commands, logging, random, re, time, utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class power_Resume(test.test):
    version = 1
    preserve_srcdir = True


    def __get_last_msg_time(self, msg):
        data = commands.getoutput(
            "grep '%s' /var/log/messages | tail -n 1" % msg)
        match = re.search(r' \[\s*([0-9.]+)\] ', data)
        if match is None:
            raise error.TestError('Failed to find log message: ' + msg)

        msg_time = float(match.group(1))
        logging.debug("Last message '%s' time = %f" % (msg, msg_time))
        return msg_time


    def __get_start_suspend_time(self):
        return self.__get_last_msg_time('Freezing user space')


    def __get_end_suspend_time(self):
        return self.__get_last_msg_time('Back to C!')

    def __get_end_resume_time(self):
        return self.__get_last_msg_time('Finishing wakeup.')


    def __is_iface_up(self, name):
        try:
            out = utils.system_output('/sbin/ifconfig %s' % name)
        except error.CmdError, e:
            logging.info(e)
            raise error.TestError('interface %s not found' % name)

        match = re.search('UP', out, re.S)
        return match


    def __sanity_check_system(self):
        time.sleep(3)

        iface = 'wlan0'
        if not self.__is_iface_up(iface):
            raise error.TestFail('%s failed to come up' % iface)


    def run_once(self):
        # Some idle time before initiating suspend-to-ram
        idle_time = random.randint(1, 10)
        time.sleep(idle_time)

        # Safe enough number, can tweek if necessary
        time_to_sleep = 10

        # Set the alarm
        alarm_time = int(utils.get_hwclock_seconds()) + time_to_sleep
        logging.debug('alarm_time = %d' % alarm_time)
        utils.set_wake_alarm(alarm_time)

        # Suspend the system to RAM
        utils.suspend_to_ram()

        # Calculate the suspend/resume times
        total_resume_time = utils.get_hwclock_seconds() - alarm_time

        # Get suspend and resume times from /var/log/messages
        start_suspend_time = self.__get_start_suspend_time()
        end_suspend_time = self.__get_end_suspend_time()
        end_resume_time = self.__get_end_resume_time()

        # The order in which processes are un-frozen is indeterminate
        # and therfore this test may get resumed before the system has gotten
        # a chance to write the end resume message. Sleep for a short time
        # to take care of this race.
        count = 0
        while end_resume_time < start_suspend_time and count < 5:
            count += 1
            time.sleep(1)
            end_resume_time = self.__get_end_resume_time()

        if count == 5:
            raise error.TestError('Failed to find end resume time')

        suspend_time = end_suspend_time - start_suspend_time
        kernel_resume_time = end_resume_time - end_suspend_time
        firmware_resume_time = total_resume_time - kernel_resume_time

        # Prepare the results
        results = {}
        results['seconds_system_suspend'] = suspend_time
        results['seconds_system_resume'] = total_resume_time
        results['seconds_system_resume_firmware'] = firmware_resume_time
        results['seconds_system_resume_kernel'] = kernel_resume_time
        self.write_perf_keyval(results)

        # Finally, sanity check critical system components
        self.__sanity_check_system()
