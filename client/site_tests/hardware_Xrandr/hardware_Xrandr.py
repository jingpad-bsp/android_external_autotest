# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging, time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

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
        if line[0:5] == 'Screen':
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


def set_xrandr_output(output_name, enable):
    """
    Sets the output given by |output_name| on or off.

    Parameters:
        output_name       name of output, e.g. 'HDMI1', 'LVDS1', 'DP1'
        enable            True or False, indicating whether to turn on or off
    """

    call_xrandr('--output %s --%s' % (output_name, 'auto' if enable else 'off'))


class hardware_Xrandr(test.test):
    version = 1

    def run_once(self):
        # Start ui if not started.  Restart if already started.  This is needed
        # because:
        #   1. X is running only when ui is running.
        #   2. Make sure the system is at the login screen instead of in a
        #      started session, so powerd will not turn off the screen.
        if utils.system_output('status ui').find('start/running') !=-1:
            utils.system_output('restart ui')
        else:
            utils.system_output('start ui')

        # Wait for X to be started so Xrandr does not get called too soon.
        time.sleep(5)

        num_errors = 0
        keyvals = {}

        # Read the Xrandr outputs.
        xrandr_state = get_xrandr_output_state()

        # Toggle each output twice and verify the output has turned on/off.
        for output in xrandr_state:
            is_enabled = xrandr_state[output]

            for output_state in [not is_enabled, is_enabled]:
                start_time = time.time();
                set_xrandr_output(output, output_state)
                end_time = time.time();

                output_state_string = 'on' if output_state else 'off'
                keyvals['set_%s_%s_time_s' % (output, output_state_string)] = \
                    end_time - start_time

                new_xrandr_state = get_xrandr_output_state()
                if new_xrandr_state[output] != output_state:
                    logging.error('Failed to turn %s %s.' %
                                  (output, output_state_string))
                    num_errors += 1
                    break

                if output_state == is_enabled:
                    logging.info('Successfully cycled output %s' % output)

        self.write_perf_keyval(keyvals)

        if num_errors > 0:
            raise error.TestFail('Failed with %d errors, see log for details' %
                                 num_errors)

    def cleanup(self):
        # Reset the UI, which may have been adjusted by Chrome when outputs were
        # turned on and off.
        utils.system_output('restart ui');