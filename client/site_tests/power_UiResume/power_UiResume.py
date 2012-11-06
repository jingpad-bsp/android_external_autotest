# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, random, re, time
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_logging, cros_ui_test, rtc, sys_power


def get_last_msg_timestamp(patterns):
    # The order in which processes are un-frozen is indeterminate
    # and therfore this test may get resumed before the system has gotten
    # a chance to finalize writes to logfile. Sleep and retry to take care of
    # this race.
    log_reader = cros_logging.LogReader(include_rotated_logs=False)
    msg = log_reader.get_last_msg(patterns, retries=5, sleep_seconds=1)
    if not msg:
        raise error.TestError(
            'Could not find a log message matching any of:\n' +
            '\n'.join(patterns ))

    timestamp = cros_logging.extract_kernel_timestamp(msg)
    return (timestamp, msg)


def get_device_resume_time():
    (_, msg) = get_last_msg_timestamp('PM: resume of devices complete after')
    match = re.search(r'PM: resume of devices complete after ([0-9.]+)',
                      msg)
    if match is None:
        raise error.TestError('Failed to find device resume time on line: '
                              + msg)
    # convert from msec to sec
    return float(match.group(1)) / 1000


def get_cpu_resume_time(start_resume):
    # systems with only one logical CPU won't have this message
    log_reader = cros_logging.LogReader(include_rotated_logs=False)
    msg = log_reader.get_last_msg(r'CPU[0-9]+ is up')
    if msg:
        t = cros_logging.extract_kernel_timestamp(msg)
        return t - start_resume
    else:
        return 0


class power_UiResume(cros_ui_test.UITest):

    version = 1


    def initialize(self, creds='$default'):
        # It's important to log in with a real user. If logged in as
        # guest, powerd will shut down instead of suspending.
        super(power_UiResume, self).initialize(creds=creds)


    def run_once(self):

        # Some idle time before initiating suspend-to-ram
        idle_time = random.randint(7, 15)
        time.sleep(idle_time)

        # Safe enough number, can tweek if necessary
        time_to_sleep = 10

        # Keep trying the suspend/resume several times to get all positive
        # time readings.
        max_num_attempts = 5
        for retry_count in range(max_num_attempts):
            # Set the alarm
            alarm_time = rtc.get_seconds() + time_to_sleep
            logging.debug('alarm_time = %d', alarm_time)
            rtc.set_wake_alarm(alarm_time)

            # Request a suspend via dbus
            sys_power.request_suspend()

            # Waiting since it can take time to react to suspend request and
            # we don't want to look at the logs before suspend.
            time.sleep(3)

            # Get suspend and resume times from /var/log/messages
            tms = {}
            for (name, patterns) in sys_power.SUSPEND_RESUME_MESSAGES.items():
                (timestamp, msg) = get_last_msg_timestamp(patterns)
                tms[name] = timestamp

            kernel_cpu_resume_time = get_cpu_resume_time(tms['START_RESUME'])
            kernel_device_resume_time = get_device_resume_time()

            suspend_time = tms['END_SUSPEND'] - tms['START_SUSPEND']
            kernel_resume_time = tms['END_RESUME'] - tms['START_RESUME']

            # if suspend time is positive it probably went ok and we can stop
            if suspend_time > 0:
                break

            # Flag an error if the max attempts have been reached without a set
            # of successful result values.
            if retry_count >= max_num_attempts - 1:
                raise error.TestError( \
                    "Negative time results, exceeded max retries.")

        # Prepare the results
        results = {}
        results['seconds_system_suspend'] = suspend_time
        results['seconds_system_resume_kernel'] = kernel_resume_time
        results['seconds_system_resume_kernel_cpu'] = kernel_cpu_resume_time
        results['seconds_system_resume_kernel_dev'] = kernel_device_resume_time
        results['num_retry_attempts'] = retry_count

        self.write_perf_keyval(results)
