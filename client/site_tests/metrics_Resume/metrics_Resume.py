# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import commands, os, time, utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class metrics_Resume(test.test):
    version = 1
    preserve_srcdir = True

#    TODO(sosa@chromium.org) - Re-add once run_remote_tests handles setup
#    def setup(self):
#        os.chdir(self.srcdir)
#        utils.system('make clean')
#        utils.system('make')

    def __get_start_suspend_time(self):
      data = commands.getoutput(
          "cat /var/log/messages | grep 'Freezing user space'"
          + " | tail -n 1 | cut -d ' ' -f 7")
      data = data.rstrip("]")
      return float(data)


    def __get_end_suspend_time(self):
      data = commands.getoutput(
          "cat /var/log/messages | grep 'CPU[0-9] is down'"
          + " | tail -n 1 | cut -d ' ' -f 7")
      data = data.rstrip("]")
      return float(data)


    def run_once(self, itersleep=None):
        if itersleep is not None:
            time.sleep(itersleep)
        # Safe enough number, can tweek if necessary
        time_to_sleep = 10

        read_hwclock = os.path.join(self.bindir, "read_hwclock")
        (status, output) = commands.getstatusoutput(read_hwclock)
        if status != 0:
            raise error.TestError('Failure to check clock')
        # Set the alarm time to 10 seconds from now
        alarm_time = int(float(output)) + time_to_sleep
        set_wake_command = 'echo ' + str(alarm_time) + \
                " > /sys/class/rtc/rtc0/wakealarm"
        if commands.getstatusoutput(set_wake_command)[0] != 0:
            raise error.TestError('Failure to set wake alarm')
        sleep_command = "echo mem > /sys/power/state"
        resume_command = sleep_command + '&&' + read_hwclock
        (status, output) = commands.getstatusoutput(resume_command)
        if status != 0:
            raise error.TestError('Failure to suspend to ram')
        resume_time = float(output) - alarm_time
        suspend_time = \
            self.__get_end_suspend_time() - self.__get_start_suspend_time()

        # Prepare Results
        results = {}
        results['seconds_system_suspend'] = suspend_time
        results['seconds_system_resume'] = resume_time
        self.write_perf_keyval(results)
