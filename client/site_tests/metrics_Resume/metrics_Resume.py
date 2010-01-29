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

    def run_once(self, itersleep=None):
        if itersleep is not None:
            time.sleep(itersleep)

        read_hwclock = os.path.join(self.bindir, "read_hwclock")
        (status, output) = commands.getstatusoutput(read_hwclock)
        if status != 0:
            raise error.TestError('Failure to check clock')
        # Set the alarm time to 10 seconds from now
        alarm_time = int(float(output)) + 10
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
        self.write_perf_keyval({'seconds_system_resume' : resume_time})
