# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, time
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui, power_status


# TODO(crosbug.com/36061): these funcs are taken from hardware_Xrandr test.
# Move them into a common library.
def call_xrandr(args_string=''):
    """
    Calls xrandr with the args given by args_string.

    |args_string| is a single string containing all arguments.
    e.g. call_xrandr('--output LVDS1 --off') will invoke:
        'xrandr --output LVDS1 --off'

    Return value: Output of xrandr
    """

    cmd = 'xrandr'
    xauth = '/home/chronos/.Xauthority'
    environment = 'DISPLAY=:0.0 XAUTHORITY=%s' % xauth
    return utils.system_output('%s %s %s' % (environment, cmd, args_string))


def get_xrandr_output_state():
    """
    Retrieves the status of display outputs using Xrandr.

    Return value: dictionary of display states.
                  key = output name
                  value = False if off, True if on
    """

    output = call_xrandr().split('\n')
    xrandr_outputs = {}
    current_output_name = ''

    # Parse output of xrandr, line by line.
    for line in output:
        if line.startswith('Screen'):
            continue
        # If the line contains "connected", it is a connected display, as
        # opposed to a disconnected output.
        if line.find(' connected') != -1:
            current_output_name = line.split()[0]
            xrandr_outputs[current_output_name] = False
            continue

        # If "connected" was not found, this is a line that shows a display
        # mode, e.g:    1920x1080      50.0     60.0     24.0
        # Check if this has an asterisk indicating it's on.
        if line.find('*') != -1 and current_output_name != '' :
            xrandr_outputs[current_output_name] = True
            # Reset the output name since this should not be set more than once.
            current_output_name = ''

    return xrandr_outputs


def get_num_outputs_on():
    """
    Retrieves the number of connected outputs that are on, using Xrandr.

    Return value: integer value of number of connected outputs that are on.
    """

    xrandr_state = get_xrandr_output_state()
    output_states = [xrandr_state[name] for name in xrandr_state]
    return sum([1 if is_enabled else 0 for is_enabled in output_states])


def wait_for_value(func,
                   min_threshold=None,
                   max_threshold=None,
                   timeout_sec=10):
    """
    Returns the value of func().  If |min_threshold| and |max_threshold| are
    not set, returns immediately.  If either of them is set, this function
    will repeatedly call func() until the return value reaches or exceeds one of
    these thresholds.

    Polling will stop after |timeout_sec| regardless of these thresholds.

    Return value:
        The most recent return value of func().
    """
    value = None
    start_time_sec = time.time()
    while True:
        value = func()
        if (min_threshold is None and max_threshold is None) or \
           (min_threshold is not None and value <= min_threshold) or \
           (max_threshold is not None and value >= max_threshold):
            break

        if time.time() - start_time_sec >= timeout_sec:
            break
        time.sleep(0.1)

    return value


class power_BacklightControl(test.test):
    version = 1
    _pref_path = '/var/lib/power_manager'
    _backup_path = '/tmp/var_log_power_manager_backup'
    # Minimum and maximum number of brightness steps expected
    # between the minimum and maximum brightness levels.
    _min_num_steps = 4
    _max_num_steps = 16
    # Minimum required percentage change in energy rate between transitions
    # (max -> min, min-> off)
    _energy_rate_change_threshold_percent = 5

    def run_once(self):
        # Require that this test be run on battery so we can measure power draw.
        status = power_status.get_status()
        if status.linepower[0].online:
            raise error.TestFail('Machine must be unplugged')

        # Start powerd if not started.  Set timeouts to delay idle events.
        # Save old prefs in a backup directory.
        pref_path = self._pref_path
        os.system('mkdir %s' % self._backup_path)
        os.system('mv %s/* %s' % (pref_path, self._backup_path))
        prefs = { 'disable_als'          : 1,
                  'react_ms'             : 30000,
                  'plugged_dim_ms'       : 7200000,
                  'plugged_off_ms'       : 9000000,
                  'plugged_suspend_ms'   : 18000000,
                  'unplugged_dim_ms'     : 7200000,
                  'unplugged_off_ms'     : 9000000,
                  'unplugged_suspend_ms' : 18000000 }
        for name in prefs:
            os.system('echo %d > %s/%s' % (prefs[name], pref_path, name))

        if utils.system_output('status powerd').find('start/running') != -1:
            os.system('restart powerd')
        else:
            os.system('start powerd')

        keyvals = {}
        num_errors = 0

        # These are the expected ratios of energy rate between max, min, and off
        # (zero) brightness levels.  e.g. when changing from max to min, the
        # energy rate must become <= (max_energy_rate * max_to_min_factor).
        max_to_min_factor = \
            1.0 - self._energy_rate_change_threshold_percent / 100.0
        min_to_off_factor = \
            1.0 - self._energy_rate_change_threshold_percent / 100.0
        off_to_max_factor = 1.0 / (max_to_min_factor * min_to_off_factor)

        # Determine the number of outputs that are on.
        starting_num_outputs_on = get_num_outputs_on()
        if starting_num_outputs_on == 0:
            raise error.TestFail('At least one display output must be on.')
        keyvals['starting_num_outputs_on'] = starting_num_outputs_on

        self._max_brightness = self._get_max_brightness()
        keyvals['max_brightness'] = self._max_brightness
        if self._max_brightness <= self._min_num_steps:
            raise error.TestFail('Must have at least %d backlight levels' %
                                 (self._min_num_steps + 1))

        keyvals['initial_brightness'] = self._get_current_brightness()

        self._wait_for_stable_energy_rate()
        keyvals['initial_power_w'] = self._get_current_energy_rate()

        self._set_brightness_to_max()

        current_brightness = \
            wait_for_value(self._get_current_brightness,
                           max_threshold=self._max_brightness)
        if current_brightness != self._max_brightness:
            num_errors += 1
            logging.error(('Failed to increase brightness to max, ' + \
                           'brightness is %d.') % current_brightness)
        else:
            self._wait_for_stable_energy_rate()
            keyvals['max_brightness_power_w'] = self._get_current_energy_rate()

        # Set brightness to minimum without going to zero.
        # Note that we don't know what the minimum brightness is, so just set
        # min_threshold=0 to use the timeout to wait for the brightness to
        # settle.
        self._set_brightness_to_min()
        current_brightness = \
            wait_for_value(self._get_current_brightness,
                           min_threshold=(self._max_brightness / 2 - 1))
        if current_brightness >= self._max_brightness / 2 or \
           current_brightness == 0:
            num_errors += 1
            logging.error('Brightness is not at minimum non-zero level: %d' %
                          current_brightness)
        else:
            self._wait_for_stable_energy_rate()
            keyvals['min_brightness_power_w'] = self._get_current_energy_rate()

        # Turn off the screen by decreasing brightness one more time with
        # allow_off=True.
        self._decrease_brightness(True)
        current_brightness = wait_for_value(self._get_current_brightness,
                                            min_threshold=0)
        if current_brightness != 0:
            num_errors += 1
            logging.error('Brightness is %d, expecting 0.' % current_brightness)

        # Wait for screen to turn off.
        num_outputs_on = \
            wait_for_value(get_num_outputs_on,
                           min_threshold=(starting_num_outputs_on - 1))
        keyvals['outputs_on_after_screen_off'] = num_outputs_on
        if num_outputs_on >= starting_num_outputs_on:
            num_errors += 1
            logging.error('At least one display must have been turned off. ' + \
                          'Number of displays on: %s' % num_outputs_on)
        else:
            self._wait_for_stable_energy_rate()
            keyvals['screen_off_power_w'] = self._get_current_energy_rate()

        # Set brightness to max.
        self._set_brightness_to_max()
        current_brightness = \
            wait_for_value(self._get_current_brightness,
                           max_threshold=self._max_brightness)
        if current_brightness != self._max_brightness:
            num_errors += 1
            logging.error(('Failed to increase brightness to max, ' + \
                           'brightness is %d.') % current_brightness)

        # Verify that the same number of outputs are on as before.
        num_outputs_on = get_num_outputs_on()
        keyvals['outputs_on_at_end'] = num_outputs_on
        if num_outputs_on != starting_num_outputs_on:
            num_errors += 1
            logging.error(('Number of displays turned on should be same as ' + \
                           'at start.  Number of displays on: %s') %
                          num_outputs_on)

        self._wait_for_stable_energy_rate()
        keyvals['final_power_w'] = self._get_current_energy_rate()

        # Energy rate must have changed significantly between transitions.
        if 'max_brightness_power_w' in keyvals and \
           'min_brightness_power_w' in keyvals and \
           keyvals['min_brightness_power_w'] >= \
               keyvals['max_brightness_power_w'] * max_to_min_factor:
            num_errors += 1
            logging.error('Power draw did not decrease enough when ' + \
                          'brightness was decreased from max to min.')

        if 'screen_off_power_w' in keyvals and \
           'min_brightness_power_w' in keyvals and \
           keyvals['screen_off_power_w'] >= \
               keyvals['min_brightness_power_w'] * min_to_off_factor:
            num_errors += 1
            logging.error('Power draw did not decrease enough when screen ' + \
                          'was turned off.')

        if num_outputs_on == starting_num_outputs_on and \
           'screen_off_power_w' in keyvals and \
           keyvals['final_power_w'] <= \
               keyvals['screen_off_power_w'] * off_to_max_factor:
            num_errors += 1
            logging.error('Power draw did not increase enough after ' + \
                          'turning screen on.')

        self.write_perf_keyval(keyvals)

        if num_errors > 0:
            raise error.TestFail('Test failed with %d errors' % num_errors)


    def cleanup(self):
        # Restore prefs, delete backup directory, and restart powerd.
        pref_path = self._pref_path
        os.system('rm %s/*' % pref_path)
        os.system('mv %s/* %s' % (self._backup_path, pref_path))
        os.system('rmdir %s' % self._backup_path)
        os.system('restart powerd')


    def _call_powerd_dbus_method(self, method_name, args=''):
        destination = 'org.chromium.PowerManager'
        path = '/org/chromium/PowerManager'
        interface = 'org.chromium.PowerManager'
        command = ('dbus-send --type=method_call --system ' + \
                   '--dest=%s %s %s.%s %s') % (destination, path, interface, \
                   method_name, args)
        utils.system_output(command)


    def _decrease_brightness(self, allow_off=False):
        self._call_powerd_dbus_method('DecreaseScreenBrightness',
                                      'boolean:%s' % \
                                      ('true' if allow_off else 'false'))


    def _increase_brightness(self):
        self._call_powerd_dbus_method('IncreaseScreenBrightness')


    def _set_brightness_to_max(self):
        """
        Increases the brightness using powerd until the brightness reaches the
        maximum value. Returns when it reaches the maximum number of brightness
        adjustments
        """
        num_steps_taken = 0
        while num_steps_taken < self._max_num_steps:
            self._increase_brightness()
            num_steps_taken += 1


    def _set_brightness_to_min(self):
        """
        Decreases the brightness using powerd until the brightness reaches the
        minimum non-zero value. Returns when it reaches the maximum number of
        brightness adjustments
        """
        num_steps_taken = 0
        while num_steps_taken < self._max_num_steps:
            self._decrease_brightness(False)
            num_steps_taken += 1


    def _get_max_brightness(self):
        cmd = 'backlight-tool --get_max_brightness'
        return int(utils.system_output(cmd).rstrip())


    def _get_current_brightness(self):
        cmd = 'backlight-tool --get_brightness'
        return int(utils.system_output(cmd).rstrip())


    def _get_current_energy_rate(self):
        return power_status.get_status().battery[0].energy_rate;


    def _wait_for_stable_energy_rate(self,
                                     max_variation_percent=5,
                                     sample_delay_sec=1,
                                     window_size=10,
                                     timeout_sec=30):
        """
        Waits for the energy rate to stablize.  Stability criterion:
            The last |window_size| samples of energy rate do not deviate from
            their mean by more than |max_variation_percent|.

        Arguments:
            max_variation_percent   Percentage of allowed deviation from mean
                                    energy rate to still be considered stable.
            sample_delay_sec        Time to wait between each reading of the
                                    energy rate.
            window_size             Number of energy rate samples required to
                                    measure stability.  If there are more
                                    samples than this amount, use only the last
                                    |window_size| values.
            timeout_sec             If stability has not been attained after
                                    this long, stop waiting.

        Return value:
            True if energy rate stabilized before timeout.
            False if timed out waiting for energy rate to stabilize.
        """
        start_time = time.time()
        samples = []
        max_variation_factor = max_variation_percent / 100.0
        while time.time() - start_time < timeout_sec:
            current_rate = self._get_current_energy_rate()

            # Remove the oldest value if the list of energy rate samples is at
            # the maximum limit |window_size|, before appending a new value.
            if len(samples) >= window_size:
                samples = samples[1:]
            samples.append(current_rate)

            mean = sum(samples) / len(samples)
            if len(samples) >= window_size and \
               max(samples) <= mean * (1 + max_variation_factor) and \
               min(samples) >= mean * (1 - max_variation_factor):
                return True

            time.sleep(sample_delay_sec)

        return False
