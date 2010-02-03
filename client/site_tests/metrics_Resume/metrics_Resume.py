# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import commands, logging, re, time, utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class metrics_Resume(test.test):
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
        return self.__get_last_msg_time('CPU[0-9] is down')


    def run_once(self, itersleep=None):
        if itersleep is not None:
            time.sleep(itersleep)

        # Safe enough number, can tweek if necessary
        time_to_sleep = 10

        # Set the alarm
        alarm_time = int(utils.get_hwclock_seconds()) + time_to_sleep
        logging.debug('alarm_time = %d' % alarm_time)
        utils.set_wake_alarm(alarm_time)

        # Suspend the system to RAM
        utils.suspend_to_ram()

        # Calculate the suspend/resume times
        resume_time = utils.get_hwclock_seconds() - alarm_time
        suspend_time = \
            self.__get_end_suspend_time() - self.__get_start_suspend_time()

        # Prepare the results
        results = {}
        results['seconds_system_suspend'] = suspend_time
        results['seconds_system_resume'] = resume_time
        self.write_perf_keyval(results)
