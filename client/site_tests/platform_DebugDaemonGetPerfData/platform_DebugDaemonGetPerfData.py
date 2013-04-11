# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus, logging, subprocess

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


class platform_DebugDaemonGetPerfData(test.test):
    """
    This autotest tests the collection of perf data.  It calls perf indirectly
    through debugd -> quipper -> perf.

    The perf data is collected both when the system is idle and when there is a
    process running in the background.

    The perf data is collected over various durations.
    """

    version = 1

    # A list of durations over which to gather perf data using quipper.
    _profile_duration_seconds = [ 0, 2, 5, 10 ]

    # Commands to repeatedly run in the background when collecting perf data
    _system_profile_commands = {
        'idle'     : 'sleep 1',
        'busy'     : 'ls',
    }


    def run_once(self, *args, **kwargs):
        """
        Primary autotest function.
        """

        bus = dbus.SystemBus()
        proxy = bus.get_object('org.chromium.debugd', '/org/chromium/debugd')
        iface = dbus.Interface(proxy, dbus_interface='org.chromium.debugd')

        keyvals = {}

        # Open /dev/null to redirect unnecessary output.
        devnull = open('/dev/null', 'w')

        for profile_type in self._system_profile_commands:
            # Repeatedly run the comand for the current profile.
            cmd = 'while true; do %s; done' % \
                self._system_profile_commands[profile_type]
            process = subprocess.Popen(cmd, stdout=devnull, shell=True)

            for duration in self._profile_duration_seconds:
                # Collect perf data from debugd.
                result = iface.GetPerfData(duration)
                logging.info('Result: %s', result)
                if not result:
                    raise error.TestFail('No perf output found: %s' % result)
                if len(result) < 10:
                    raise error.TestFail('Perf output too small')

                keyvals['perf_data_size_%s_%d' % (profile_type, duration)] = \
                    len(result)

            # Terminate the process and actually wait for it to terminate.
            process.terminate()
            while process.poll() == None:
                pass

        devnull.close()

        self.write_perf_keyval(keyvals)
