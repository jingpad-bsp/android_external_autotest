# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import commands, logging, random, re, time
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import rtc, sys_power, cros_logging

from autotest_lib.client.cros import flimflam_test_path
import flimflam


# TODO(cychiang/jsalz): Use cros.factory.goofy.time_sanitizer.CheckHwclock.
def CheckHwclock():
  '''Check hwclock is working by a write(retry once if fail) and a read.'''
  for _ in xrange(2):
    logging.info('Setting hwclock')
    if utils.system('hwclock -w --utc --noadjfile', ignore_status=True) == 0:
      break
    else:
      logging.error('Unable to set hwclock time')

  logging.info('Current hwclock time: %s' %
      utils.system_output('hwclock -r'))


class power_Resume(test.test):
    version = 1
    preserve_srcdir = True


    def _get_key_name_from_dev_name(self, key_name):
        """Transform a string in such a way that it will be accepted by
        autotest framework as a key.

        A device name will contain ':' and '+'. Autotest doesn't allows these
        characters in the key.

        Args:
            key_name: The string that it will be transformed.

        Return:
            A new string that autotest will accept as a key name.
        """

        return key_name.replace(':', '-').replace('+', '_')


    def _get_sr_time_for_each_device(self, sus_time, res_time):
        """Get how much time each device took to suspend/resume in a certain
        interval.

            Args:
                sus_time: The time interval for suspend messages (in dmesg
                    timestamps) described as a tuple. Where sus_time[0] is the
                    start of the interval and sus_time[1] is the end of the
                    interval. If the interval is badly specified (i.e.
                    sus_time[0] > sus_time[1]) then no suspend message is
                    extracted/parsed and a warning is logged.
                res_time: The time interval for resume messages (in dmesg
                    timestamps) described as a tuple. Similar format as
                    sus_time argument.

            Return:
                A dictionary with the following key format:
                seconds_dev_<devname>_<action>.  Where <devname> is the name of
                the device (escaped in such a way that autotest will accept the
                string as key) and <action> one of the following strings:
                'resume' or 'suspend'. The value is the number of seconds (as a
                float) that it took for <devname> to do a suspend or a resume.

            Raise:
                TestError: If the log is corrupted.
        """

        sr_time = {}
        call_regexp = re.compile(r'call ([^ ]+) returned 0 after ([0-9]+) '
                'usecs')

        if sus_time[0] > sus_time[1]:
            logging.error("Suspend interval is wrong.")

        if res_time[0] > res_time[1]:
            logging.error("Resume interval is wrong.")

        for dev_line in self._log_msg.get_logs().splitlines():
            # find the time stamp for each message
            ts = -1
            try:
                ts = cros_logging.extract_kernel_timestamp(dev_line)
            except error.TestError:
                # probabily not an interesting message
                continue

            is_suspend = None

            if ts >= sus_time[0] and ts <= sus_time[1]:
                is_suspend = True

            if ts >= res_time[0] and ts <= res_time[1]:
                is_suspend = False

            if is_suspend is None:
                # skip this message, because it's in a different interval
                continue

            # extract the device name and device time
            search_groups = call_regexp.search(dev_line)

            if search_groups is None:
                # this line doesn't contains a call string
                continue

            (device_name, time_matched) = search_groups.groups()
            device_time = float(time_matched)

            action = 'suspend' if is_suspend else 'resume'

            # convert from usec to seconds and save the result
            device_name_key = 'seconds_dev_' + \
                self._get_key_name_from_dev_name(device_name) + '_' + action

            if sr_time.has_key(device_name_key):
                logging.warn("Duplicate entry for %s (%s)." %
                    (device_name, action))

            sr_time[device_name_key] = device_time / 1e6

            logging.debug("%s = %s", device_name_key, sr_time[device_name_key])

        return sr_time


    def _get_last_msg(self, patterns):
        return self._log_msg.get_last_msg(patterns,
                retries=5, sleep_seconds=1)


    def _get_last_msg_time(self, patterns):
        """Extract timestamp from a message which matches a certain pattern(s).

        Args:
            patterns: Pattern or list of patterns that the message will match.

        Returns:
            The timestamp from the last matched message or -1 if we couldn't
            match a message.

        Raises:
            TestError: If the timestamp could not be extracted from the matched
            pattern.
        """
        msg = self._get_last_msg(patterns)

        if msg is None:
            # we didn't find the pattern
            return -1
        else:
            return cros_logging.extract_kernel_timestamp(msg)


    def _get_end_cpu_resume_time(self):
        # systems with only one logical CPU won't have this message, return -1
        time = self._get_last_msg_time('CPU[0-9]+ is up')
        logging.debug('END cpu resume time %f' % time)

        return time


    def _get_start_suspend_time(self):
        time = self._get_last_msg_time(
                sys_power.SUSPEND_RESUME_MESSAGES['START_SUSPEND'])
        if time == -1:
            raise error.TestError("Could not find start suspend time message.")
        logging.debug('START suspend time: %f' % time)

        return time


    def _get_end_suspend_time(self):
        time = self._get_last_msg_time(
                sys_power.SUSPEND_RESUME_MESSAGES['END_SUSPEND'])
        if time == -1:
            raise error.TestError("Could not find end suspend time message.")
        logging.debug('END suspend time %f' % time)

        return time


    def _get_start_resume_time(self):
        time = self._get_last_msg_time(
                sys_power.SUSPEND_RESUME_MESSAGES['START_RESUME'])
        if time == -1:
            raise error.TestError("Could not find start resume time message.")
        logging.debug('START resume time %f' % time)

        return time


    def _get_end_resume_time(self):
        time = self._get_last_msg_time(
                sys_power.SUSPEND_RESUME_MESSAGES['END_RESUME'])
        if time == -1:
            raise error.TestError("Could not find end resume time message.")
        logging.debug('END resume time %f' % time)

        return time


    def _get_device_resume_time(self):
        data = self._get_last_msg("PM: resume of devices complete after")
        match = re.search(r'PM: resume of devices complete after ([0-9.]+)',
                          data)
        if match is None:
            raise error.TestError('Failed to find device resume time on line: '
                                  + data)
        logging.debug('device resume time: %f' % (float(match.group(1))/1e3))

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


    def run_once(self, max_devs_returned=10):
        # Check hwclock is working
        CheckHwclock()

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

        sr_time_for_devs = {}

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

            # initialize LogReader object
            self._log_msg = \
                cros_logging.LogReader(include_rotated_logs=False)

            # Get suspend and resume times from /var/log/messages
            start_suspend_time = self._get_start_suspend_time()
            end_suspend_time = self._get_end_suspend_time()
            start_resume_time = self._get_start_resume_time()
            end_resume_time = self._get_end_resume_time()
            end_cpu_resume_time = self._get_end_cpu_resume_time()
            kernel_device_resume_time = self._get_device_resume_time()

            sr_time_for_devs = \
                self._get_sr_time_for_each_device(
                    (start_suspend_time, end_suspend_time),
                    (start_resume_time, end_resume_time))

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

        # return as keyvals the slowest n devices
        slowest_devs = sorted(
            sr_time_for_devs,
            key=sr_time_for_devs.get,
            reverse=True)[:max_devs_returned]
        for dev in slowest_devs:
            results[dev] = sr_time_for_devs[dev]

        results['seconds_system_suspend'] = suspend_time
        results['seconds_system_resume'] = total_resume_time
        results['seconds_system_resume_firmware'] = firmware_resume_time
        results['seconds_system_resume_kernel'] = kernel_resume_time
        results['seconds_system_resume_kernel_cpu'] = kernel_cpu_resume_time
        results['seconds_system_resume_kernel_dev'] = kernel_device_resume_time
        results['seconds_3G_disconnect'] = disconnect_3G_time
        results['num_retry_attempts'] = retry_count

        self.write_perf_keyval(results)


    def cleanup(self):
        self._disable_pm_print_times()
