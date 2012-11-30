# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, time

import common
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error, enum
from autotest_lib.client.cros import cros_logging, rtc, sys_power
from autotest_lib.client.cros import flimflam_test_path
import flimflam


class SuspendFailure(error.TestFail):
    """Base class for a failure during a single suspend/resume cycle."""
    pass


class HwClockError(SuspendFailure):
    """Known bug with firmware messing up RTC interrupts (crosbug.com/36004)"""
    AFFECTED_BOARDS = ['LUMPY', 'STUMPY', 'KIEV']
    @staticmethod
    def is_affected():
        """Returns True iff the current board is known to be affected."""
        return utils.get_board() in HwClockError.AFFECTED_BOARDS


class FirmwareError(SuspendFailure):
    """String 'ERROR' found in firmware log after resume."""
    WHITELIST = [r'PNP: 002e\.4 70 irq size: 0x0000000001 not assigned']


class KernelError(SuspendFailure):
    """Kernel BUG or WARNING during suspend/resume."""
    pass


class Suspender(object):
    """Class for suspend/resume measurements.

    Public attributes:
        disconnect_3G_time: Amount of seconds it took to disable 3G.
        successes[]: List of timing measurement dicts from successful suspends.
        failures[]: List of SuspendFailure exceptions from failed suspends.
        device_times[]: List of individual device suspend/resume time dicts.

    Public methods:
        suspend: Do a suspend/resume cycle. Return timing measurement dict.

    Private attributes:
        _log_reader: LogReader that is set to start right before suspending.
        _logged_failures: Last read amount of suspend failures since boot.
        _use_dbus: Set to use asynchronous DBus method for suspending.
        _throw: Set to have SuspendFailure exceptions raised to the caller.
        _reset_pm_print_times: Set to deactivate pm_print_times after the test.
        _restart_tlsdated: Set to restart tlsdated after the test.

    Private methods:
        __init__: Shuts off tlsdated for duration of test, disables 3G
        __del__: Restore tlsdated (must run eventually, but GC delay no problem)
        _set_pm_print_times: Enable/disable kernel device suspend timing output.
        _check_failure_log: Check /sys/.../suspend_stats for new failures.
        _ts: Returns a timestamp from _log_reader for a sys_power pattern.
        _hwclock_ts: Read RTC timestamp left on resume in hwclock-on-resume
        _device_resume_time: Read seconds overall device resume took from logs.
        _individual_device_times: Reads individual device suspend/resume times.
    """
    def __init__(self, use_dbus=False, throw=False, device_times=False):
        """Prepare environment for suspending."""
        self.disconnect_3G_time = 0
        self.successes = []
        self.failures = []
        self._use_dbus = use_dbus
        self._throw = throw
        self._reset_pm_print_times = False
        self._restart_tlsdated = False
        self._log_reader = cros_logging.LogReader()
        self._logged_failures = 0
        self._check_failure_log()
        if device_times:
            self.device_times = []

        # stop tlsdated, make sure we/hwclock have /dev/rtc for ourselves
        if utils.system_output('initctl status tlsdated').find('start') != -1:
            utils.system('initctl stop tlsdated')
            self._restart_tlsdated = True

        # prime powerd_suspend RTC timestamp saving and make sure hwclock works
        utils.open_write_close('/var/run/power_manager/hwclock-on-resume', '')
        hwclock_output = utils.system_output('hwclock -r --debug --utc',
                                             ignore_status=True)
        if hwclock_output.find('Using /dev interface') == -1:
            raise error.TestError('hwclock cannot find rtc: ' + hwclock_output)

        # activate device suspend timing debug output
        if hasattr(self, 'device_times'):
            if not int(utils.read_one_line('/sys/power/pm_print_times')):
                self._set_pm_print_times(True)
                self._reset_pm_print_times = True

        # Shut down 3G to remove its variability from suspend time measurements
        flim = flimflam.FlimFlam()
        service = flim.FindCellularService(0)
        if service:
            logging.info('Found 3G interface, disconnecting.')
            start_time = time.time()
            (success, status) = flim.DisconnectService(
                    service=service, wait_timeout=60)
            if success:
                logging.info('3G disconnected successfully.')
                self.disconnect_3G_time = time.time() - start_time
            else:
                logging.error('Could not disconnect: %s.' % status)
                self.disconnect_3G_time = -1


    def __del__(self):
        """Restore normal environment (not turning 3G back on for now...)"""
        os.remove('/var/run/power_manager/hwclock-on-resume')
        if self._restart_tlsdated:
            utils.system('initctl start tlsdated')
        if self._reset_pm_print_times:
            self._set_pm_print_times(False)


    def _set_pm_print_times(self, on):
        """Enable/disable extra suspend timing output from powerd to syslog."""
        if utils.system('echo %s > /sys/power/pm_print_times' % int(bool(on)),
                ignore_status=True):
            logging.warn('Failed to set pm_print_times to %s' % bool(on))
            del self.device_times
            self._reset_pm_print_times = False
        else:
            logging.info('Device resume times set to %s' % bool(on))


    def _check_failure_log(self):
        """Returns True iff there was a new suspend failure since last call."""
        old = self._logged_failures
        self._logged_failures = int(re.search(r'^fail: (\d+)$', utils.read_file(
                '/sys/kernel/debug/suspend_stats'), re.M).group(1))
        return self._logged_failures > old


    def _ts(self, name, retries=3):
        """Searches logs for last timestamp with a given suspend message."""
        # Occasionally need to retry due to races from process wakeup order
        line = self._log_reader.get_last_msg(
                sys_power.SUSPEND_RESUME_MESSAGES[name], retries=retries)
        if line:
            return cros_logging.extract_kernel_timestamp(line)
        else:
            raise error.TestError('Could not find a %s message.' % name)


    def _hwclock_ts(self, not_before, retries=3):
        """Read the RTC resume timestamp saved by powerd_suspend."""
        path = '/var/run/power_manager/hwclock-on-resume'
        for _ in xrange(retries + 1):
            if os.path.exists(path):
                match = re.search(r'([0-9]+) seconds since .+ (-?[0-9.]+) sec',
                                  utils.read_file(path), re.DOTALL)
                if match:
                    seconds = int(match.group(1)) + float(match.group(2))
                    if seconds < not_before: continue
                    logging.debug('RTC resume timestamp read: %f' % seconds)
                    return seconds
            time.sleep(0.2)
        logging.debug('HwClock failure, dumping nvram:\n' +
                utils.system_output('mosys nvram dump'))
        raise HwClockError('RTC timestamp broken:' + utils.read_file(path))


    def _firmware_resume_time(self):
        """Calculate seconds for firmware resume from logged TSC. (x86 only)"""
        if utils.get_arch() not in ['i686', 'x86_64']:
            # TODO: support this on ARM somehow
            return 0
        pattern = r'TSC at resume: (\d+)$'
        line = self._log_reader.get_last_msg(pattern)
        if line:
            freq = 1000 * int(utils.read_one_line(
                    '/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq'))
            return float(re.search(pattern, line).group(1)) / freq
        raise error.TestError('Failed to find TSC resume value in syslog.')


    def _device_resume_time(self):
        """Read amount of seconds for overall device resume from syslog."""
        pattern = r'PM: resume of devices complete after ([0-9.]+)'
        line = self._log_reader.get_last_msg(pattern)
        if line:
            return float(re.search(pattern, line).group(1)) / 1000
        raise error.TestError('Failed to find device resume time in syslog.')


    def _individual_device_times(self, start_resume):
        """Return dict of individual device suspend and resume times."""
        self.device_times.append(dict())
        regex = re.compile(r'call ([^ ]+)\+ returned 0 after ([0-9]+) usecs')
        for line in self._log_reader.read_all_logs():
            match = regex.search(line)
            if match:
                key = 'seconds_dev_' + match.group(1).replace(':', '-')
                secs = float(match.group(2)) / 1e6
                if cros_logging.extract_kernel_timestamp(line) > start_resume:
                    key += '_resume'
                else:
                    key += '_suspend'
                if key in self.device_times[-1]:
                    logging.warn('Duplicate entry for %s: +%f' % (key, secs))
                    self.device_times[-1][key] += secs
                else:
                    logging.debug('%s: %f' % (key, secs))
                    self.device_times[-1][key] = secs


    def suspend(self, duration=10):
        """
        Do a single suspend for 'duration' seconds. Returns None on errors, or
        raises the exception when _throw is set. Returns a dict of general
        measurements, or a tuple (general_measurements, individual_device_times)
        when _device_times is set.
        """
        iteration = len(self.failures) + len(self.successes) + 1
        self._log_reader.set_start_by_current()
        try:
            # set the RTC alarm
            alarm_time = int(rtc.get_seconds() + duration)
            logging.debug('Trying suspend %d for %d seconds... wakealarm = %d' %
                          (iteration, duration, alarm_time))
            rtc.set_wake_alarm(alarm_time)
            if len(rtc.get_rtc_devices()) > 1:
                rtc.set_wake_alarm(alarm_time + 15, 'rtc1')

            # do the actual suspend
            if self._use_dbus:
                # asynch suspend, need to wait a while for it to happen...
                sys_power.request_suspend()
                # TODO: replace sleep with listening for DBus resume message
                time.sleep(3)
            else:
                sys_power.suspend_to_ram()

            # look for errors
            if os.path.exists('/sys/firmware/log'):
                for msg in re.findall(r'^.*ERROR.*$',
                        utils.read_file('/sys/firmware/log'), re.M):
                    for pattern in FirmwareError.WHITELIST:
                        if re.search(pattern, msg):
                            logging.info('Whitelisted firmware error: ' + msg)
                            break
                    else:
                        raise FirmwareError(msg.strip('\r\n '))

            regex = re.compile(r' kernel: \[.*(BUG:|WARNING:|CRC.*error)')
            for line in self._log_reader.read_all_logs():
                if regex.search(line):
                    raise KernelError(line)
            if self._check_failure_log():
                raise SuspendFailure('Unidentified suspend failure.')

            # calculate general measurements
            start_resume = self._ts('START_RESUME')
            kernel_down = self._ts('END_SUSPEND') - self._ts('START_SUSPEND')
            kernel_up = self._ts('END_RESUME') - start_resume
            devices_up = self._device_resume_time()
            total_up = self._hwclock_ts(alarm_time) - alarm_time
            firmware_up = self._firmware_resume_time()
            board_up = total_up - kernel_up - firmware_up
            try:
                cpu_up = self._ts('CPU_READY', 0) - start_resume
            except error.TestError:
                # can be missing on non-SMP machines
                cpu_up = None
            if total_up > 15:
                raise SuspendFailure('Duration too short, backup RTC fired!')

            logging.debug('Success(%d): %g down, %g up, %g board, %g firmware, '
                          '%g kernel, %g cpu, %g devices' %
                          (iteration, kernel_down, total_up, board_up,
                           firmware_up, kernel_up, cpu_up, devices_up))
            self.successes.append({
                'seconds_system_suspend': kernel_down,
                'seconds_system_resume': total_up,
                'seconds_system_resume_firmware': firmware_up + board_up,
                'seconds_system_resume_firmware_cpu': firmware_up,
                'seconds_system_resume_firmware_ec': board_up,
                'seconds_system_resume_kernel': kernel_up,
                'seconds_system_resume_kernel_cpu': cpu_up,
                'seconds_system_resume_kernel_dev': devices_up,
                })

            if hasattr(self, 'device_times'):
                self._individual_device_times(start_resume)
                return (self.successes[-1], self.device_times[-1])
            else:
                return self.successes[-1]

        except SuspendFailure as ex:
            logging.error('%s(%d): %s' % (type(ex).__name__, iteration, ex))
            self.failures.append(ex)
            if self._throw: raise
            return None
