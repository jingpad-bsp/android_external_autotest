# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging, time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import base_utils, error


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
        xrandr_state = base_utils.get_xrandr_output_state()

        # Toggle each output twice and verify the output has turned on/off.
        for output in xrandr_state:
            is_enabled = xrandr_state[output]

            for output_state in [not is_enabled, is_enabled]:
                start_time = time.time();
                base_utils.set_xrandr_output(output, output_state)
                end_time = time.time();

                output_state_string = 'on' if output_state else 'off'
                xrandr_time_s = end_time - start_time

                if self._is_internal(output):
                    keyvals['internal_output_name'] = output
                    keyvals['s_internal_%s_time' % (output_state_string)] = \
                            xrandr_time_s
                else:
                    keyvals['s_%s_%s_time' % (output, output_state_string)] = \
                            xrandr_time_s

                new_xrandr_state = base_utils.get_xrandr_output_state()
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
        if utils.system_output('status ui').find('start/running') !=-1:
            utils.system_output('restart ui')
        else:
            utils.system_output('start ui')


    def _is_internal(self, output):
        """
        Determines if the given output is an internal output.  Internal outputs
        are identified by name -- either eDP or LVDS.

        Args:
          output:     name of output to check
        Return value:
          True if |output| is eDP or LVDS, False otherwise.
        """
        internal_types = ['edp', 'lvds']
        matches = [output.lower().startswith(type) for type in internal_types]
        return True in matches
