# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import commands, logging, random, re, time
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import rtc, sys_power

from autotest_lib.client.cros import flimflam_test_path
import flimflam

START_SUSPEND_MESSAGES = [ 'Freezing user space' ]
END_SUSPEND_MESSAGES = [ 'Back to C!', 'Low-level resume complete',
                         'Entering suspend state', 'sleep: irq wakeup masks:' ]
START_RESUME_MESSAGES = [ 'Back to C!', 'Low-level resume complete',
                          'Suspended for', 'Resume caused by',
                          'post sleep, preparing to return']
END_RESUME_MESSAGES = [ 'Restarting tasks' ]

class power_Resume(test.test):
    version = 1
    preserve_srcdir = True


    def _get_command_output(self, cmd):
        """Try to execute a command, until we get some output or a limit is
        reached.

        The order in which processes are un-frozen is indeterminate
        and therfore this test may get resumed before the system has gotten
        a chance to finalize writes to logfile. Sleep a bit to take care of
        this race.

        Args:
            cmd: The command to execute.

        Returns:
            The output of the command that was executed, or None, if the
            command didn't printed anything to standard output.
        """
        count = 0
        data = commands.getoutput(cmd)
        while len(data) == 0 and count < 5:
            count +=1
            time.sleep(1)
            data = commands.getoutput(cmd)

        if count == 5:
            return None

        return data


    def _get_last_msg(self, pattern):
        """Search for the last message in /var/log/messages, that matches a
        given pattern.

            Args:
                pattern: The pattern for which we search.

            Return:
                If the pattern is found in /var/log/messages, the last line
                that matches that pattern.

            Raises:
                TestError: If the pattern isn't found.
        """
        cmd = "grep -a '%s' /var/log/messages | tail -n 1" % pattern
        data = self._get_command_output(cmd)
        if data is None:
            raise error.TestError("Did not find log message: " + pattern)
        return data


    def _get_max_time_device(self, start, stop, action):
        """Get the device (name and time) that had the longest suspend or
        resume time in a certain interval.

            Args:
                start: The beginning of the time interval (in dmesg
                    timestamps).
                stop: The ending of the time interval (in dmesg timestamps).
                action: "suspend" or "resume", used only for logging.

            Return:
                A tuple containing the name of the slowest device and the time
                that it took to suspend or resume or (None, 0) if no such
                device could be found.

            Raise:
                TestError: If no device was found in *any* interval or if the
                log is corrupted.
        """
        cmd = "grep -a 'call [^ ]\+ returned 0 after [0-9]\+ usecs' " + \
            "/var/log/messages"
        data = self._get_command_output(cmd)

        if data is None:
            raise error.TestError("Did not find any device")

        max_time = 0
        max_device_name = None
        call_regexp = re.compile(r'call ([^ ]+) returned 0 after ([0-9]+) '
                'usecs')
        for dev_line in data.splitlines():
            # find the time stamp for each message
            match_ts = re.search(r' \[\s*([0-9.]+)\] ', dev_line)
            if match_ts is None:
                raise error.TestError('Did not find timestamp for log message: '
                        + dev_line)
            ts = float(match_ts.group(1))

            if not (ts >= start and ts <= stop):
                # skip this message, because it's in a different interval
                continue

            # extract the device name and device time
            search_groups = call_regexp.search(dev_line)

            if search_groups is None:
                # this line doesn't contains a call string
                continue

            (device_name, time) = search_groups.groups()
            device_time = float(time)

            logging.debug("Device %s took %s to %s" % \
                    (device_name, device_time, action))

            # calculate the maximal time
            if device_time > max_time:
                max_time = device_time
                max_device_name = device_name

        # convert from usec to seconds
        return (max_device_name, max_time / 1e6)

    def _get_last_msg_time(self, msg):
        data = self._get_last_msg(msg)
        match = re.search(r' \[\s*([0-9.]+)\] ', data)
        if match is None:
            raise error.TestError('Did not find timestamp for log message: '
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

    def _get_start_resume_time(self):
        time = self._get_last_msg_time_multiple(START_RESUME_MESSAGES)
        if time == -1:
            raise error.TestError("Could not find start resume time message.")

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
            hwclock_output = utils.read_file('/var/run/power_manager/'+
                                             'hwclock-on-resume')
            logging.debug('hwclock_output: ' + hwclock_output)
            match = re.search(
                    r'= ([0-9]+) seconds since .+ (-?[0-9.]+) seconds$',
                    hwclock_output, re.DOTALL)
            if match:
                seconds = int(match.group(1)) + float(match.group(2))
                logging.debug('hwclock seconds = %f' % seconds)
                return seconds

            # hwclock-on-resume file doesn't contain valid data. Retry
            count += 1
            time.sleep(1)

        raise ValueError('Unable to read the hardware clock -- ' +
                         hwclock_output)

    def _set_pm_print_times(self, enabled):
        cmd = 'echo %s > /sys/power/pm_print_times' % int(bool(enabled))
        (status, output) = commands.getstatusoutput(cmd)
        if status != 0:
            logging.warn('Failed to set pm_print_times to %s' % bool(enabled))
        else:
            logging.info('Device resume times set to %s' % bool(enabled))

    def _enable_pm_print_times(self):
        self._set_pm_print_times(True)

    def _disable_pm_print_times(self):
        self._set_pm_print_times(False)

    def run_once(self):
        # Disconnect from 3G network to take out the variability of
        # disconnection time from suspend_time
        disconnect_3G_time = 0
        flim = flimflam.FlimFlam()
        service = flim.FindCellularService()
        if service:
            logging.info('Found 3G interface, disconnecting.')
            start_time = time.time()
            success, status = flim.DisconnectService(
                service=service,
                wait_timeout=60)
            disconnect_3G_time = time.time() - start_time
            if success:
                logging.info('3G disconnected successfully.')
            else:
                logging.error('Could not disconnect: %s.' % status)
                disconnect_3G_time = -1

        self._enable_pm_print_times()
        # Some idle time before initiating suspend-to-ram
        idle_time = random.randint(1, 10)
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

            # Suspend the system to RAM
            sys_power.suspend_to_ram()

            # Get suspend and resume times from /var/log/messages
            start_suspend_time = self._get_start_suspend_time()
            end_suspend_time = self._get_end_suspend_time()
            start_resume_time = self._get_start_resume_time()
            end_resume_time = self._get_end_resume_time()
            end_cpu_resume_time = self._get_end_cpu_resume_time()
            kernel_device_resume_time = self._get_device_resume_time()

            (max_device_name_suspend, max_device_time_suspend) = \
                    self._get_max_time_device(
                            start_suspend_time,
                            end_suspend_time,
                            "suspend")

            (max_device_name_resume, max_device_time_resume) = \
                    self._get_max_time_device(
                            start_resume_time,
                            end_resume_time,
                            "resume")

            # Calculate the suspend/resume times
            total_resume_time = self._get_hwclock_seconds() - alarm_time
            suspend_time = end_suspend_time - start_suspend_time
            kernel_resume_time = end_resume_time - start_resume_time

            kernel_cpu_resume_time = 0
            if end_cpu_resume_time > 0:
                kernel_cpu_resume_time = end_cpu_resume_time - start_resume_time

            firmware_resume_time = total_resume_time - kernel_resume_time

            # If the values all came out to be nonnegative, it means success, so
            # exit the retry loop.
            if suspend_time >= 0 and total_resume_time >= 0 and \
               firmware_resume_time >= 0:
                break

            # Flag an error if the max attempts have been reached without a set
            # of successful result values.
            if retry_count >= max_num_attempts - 1:
                raise error.TestError( \
                    "Negative time results, exceeded max retries.")

        # Prepare the results
        results = {}
        results['seconds_system_suspend'] = suspend_time
        results['seconds_system_resume'] = total_resume_time
        results['seconds_system_resume_firmware'] = firmware_resume_time
        results['seconds_system_resume_kernel'] = kernel_resume_time
        results['seconds_system_resume_kernel_cpu'] = kernel_cpu_resume_time
        results['seconds_system_resume_kernel_dev'] = kernel_device_resume_time
        results['seconds_3G_disconnect'] = disconnect_3G_time
        results['num_retry_attempts'] = retry_count
        results['seconds_max_device_suspend'] = max_device_time_suspend
        results['max_device_name_suspend'] = max_device_name_suspend
        results['seconds_max_device_resume'] = max_device_time_resume
        results['max_device_name_resume'] = max_device_name_resume
        self.write_perf_keyval(results)


    def cleanup(self):
        self._disable_pm_print_times()
