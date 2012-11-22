# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, errno, shutil, os
from autotest_lib.client.bin import test, utils
from autotest_lib.client.cros import rtc, sys_power
from autotest_lib.client.common_lib import error

SLEEP_TIME = 10

SYSFS_CONSOLE_SUSPEND = '/sys/module/printk/parameters/console_suspend'

class power_NoConsoleSuspend(test.test):
    """Test suspend/resume with no_console_suspend option set."""

    version = 1

    def initialize(self):
        # Save & disable console_suspend module param
        self.old_console_suspend = utils.read_file(SYSFS_CONSOLE_SUSPEND)
        utils.write_one_line(SYSFS_CONSOLE_SUSPEND, 'N')

    def run_once(self):
        # Save wakeup count. If the wakealarm (set below) fires before
        # suspend completes, this forces the system to wake back up rather
        # than sleep forever ("suspend took too long" case below).
        try:
            wakeup_count = sys_power.read_wakeup_count()
            sys_power.write_wakeup_count(wakeup_count)
        except sys_power.ConcurrentWakeEventException:
            # Some wakeup source incremented wakeup_count. This could happen
            # due to unexpected input from the keyboard/touchpad/lid switch.
            raise error.TestError('spurious wake events')

        # Set wake alarm
        start_time = rtc.get_seconds()
        alarm_time = start_time + SLEEP_TIME
        rtc.set_wake_alarm(alarm_time)

        # Kick off the suspend
        try:
            utils.suspend_to_ram()
        except IOError as e:
            logging.exception('suspend failed')
            if e.errno == errno.EBUSY and rtc.get_seconds() >= alarm_time:
                # The wakealarm probably fired on the way to suspend.
                raise error.TestError('suspend took too long')
            else:
                # Some driver probably failed to suspend properly.
                raise error.TestError('suspend failed')

        # Save performance stats
        time_in_suspend = rtc.get_seconds() - start_time
        results = {
            'time_in_suspend': time_in_suspend,
        }
        self.write_perf_keyval(results)

        # Sanity check: slept for enough time?
        if time_in_suspend < SLEEP_TIME:
            raise error.TestError('woke from suspend early')

    def save_log_file(self, path):
        logging.info('saving log file %s', path)
        shutil.copyfile(path,
            os.path.join(self.outputdir, os.path.basename(path)))

    def cleanup(self):
        # Restore old console_suspend module param
        logging.info('restoring value for console_suspend: %s',
                     self.old_console_suspend)
        utils.open_write_close(SYSFS_CONSOLE_SUSPEND, self.old_console_suspend)

        # Save diagnostic logs
        self.save_log_file('/sys/kernel/debug/suspend_stats')
