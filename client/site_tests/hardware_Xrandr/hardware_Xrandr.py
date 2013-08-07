# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging, time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import base_utils, error


class hardware_Xrandr(test.test):
    version = 1

    def run_once(self, num_iterations=1):
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

        # Also create lists of on/off times for each output.  Initialize them to
        # zeros to avoid the overhead of appending values.
        on_times = {}
        off_times = {}
        for output in xrandr_state:
            # Attempt to identify the internal display.  Note that there may not
            # be such a display, e.g. on a desktop system.
            if self._is_internal(output):
                keyvals['internal_output_name'] = output
            on_times[output] = [0] * num_iterations
            off_times[output] = [0] * num_iterations

        # Toggle each output twice and verify the output has turned on/off.
        for index in xrange(num_iterations):
            for output in xrandr_state:
                is_enabled = xrandr_state[output]

                for output_state in [not is_enabled, is_enabled]:
                    start_time = time.time()
                    base_utils.set_xrandr_output(output, output_state)
                    end_time = time.time()

                    new_xrandr_state = base_utils.get_xrandr_output_state()
                    if new_xrandr_state[output] != output_state:
                        logging.error('Failed to turn %s %s.' %
                                      (output, 'on' if output_state else 'off'))
                        num_errors += 1
                        break

                    time_list = \
                            (on_times if output_state else off_times)[output]
                    time_list[index] = end_time - start_time

                    if output_state == is_enabled:
                        logging.info('Successfully cycled output %s' % output)

        stats = { 'mean'    : lambda list: sum(list) / num_iterations,
                  'max'     : max,
                  'min'     : min }
        for output in xrandr_state:
            output_name = output
            if self._is_internal(output):
                output_name = 'internal'

            for func_name in stats:
                keyvals['s_%s_on_%s_time' % (output_name, func_name)] = \
                        stats[func_name](on_times[output])
                keyvals['s_%s_off_%s_time' % (output_name, func_name)] = \
                        stats[func_name](off_times[output])

            logging.info(str(on_times[output]))
            logging.info(str(off_times[output]))

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
        are identified by name -- eDP, LVDS, or DSI.

        Args:
          output:     name of output to check
        Return value:
          True if |output| is eDP, LVDS, or DSI, False otherwise.
        """
        internal_types = ['edp', 'lvds', 'dsi']
        matches = [output.lower().startswith(type) for type in internal_types]
        return True in matches
