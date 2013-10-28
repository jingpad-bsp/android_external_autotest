# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cStringIO, dbus, gzip, logging, subprocess

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

    _dbus_debugd_object = '/org/chromium/debugd'
    _dbus_debugd_name = 'org.chromium.debugd'

    def gzip_string(self, string):
        """
        Gzip a string.

        @param string: The input string to be gzipped.

        Returns:
          The gzipped string.
        """
        string_file = cStringIO.StringIO()
        gzip_file = gzip.GzipFile(fileobj=string_file, mode='wb')
        gzip_file.write(string)
        gzip_file.close()
        return string_file.getvalue()


    def validate_get_perf_method(self, get_perf_method, duration, profile_type):
        """
        Validate a debugd method that returns perf data.

        @param get_perf_method: The debugd method to test.

        @param duration: The duration to use for perf data collection.

        @param profile_type: A label to use for storing into perf keyvals.
        """
        bus = dbus.SystemBus()
        proxy = bus.get_object(self._dbus_debugd_name, self._dbus_debugd_object)
        iface = dbus.Interface(proxy, dbus_interface=self._dbus_debugd_name)
        iface_function = getattr(iface, get_perf_method)
        result = iface_function(duration)
        if not result:
            raise error.TestFail('No perf output found: %s' % result)
        logging.info('%s() for %s seconds returned %d items', get_perf_method,
                     duration, len(result))
        if len(result) < 10:
            raise error.TestFail('Perf output too small')

        result = ''.join(chr(b) for b in result)
        key = '%s_size_%s_%d' % (get_perf_method, profile_type, duration)
        keyvals = {}
        keyvals[key] = len(result)
        keyvals[key + '_zipped'] = len(self.gzip_string(result))
        self.write_perf_keyval(keyvals)


    def run_once(self, *args, **kwargs):
        """
        Primary autotest function.
        """

        get_perf_methods = ['GetPerfData', 'GetRichPerfData']

        # Open /dev/null to redirect unnecessary output.
        devnull = open('/dev/null', 'w')

        for profile_type in self._system_profile_commands:
            # Repeatedly run the comand for the current profile.
            cmd = 'while true; do %s; done' % \
                self._system_profile_commands[profile_type]
            process = subprocess.Popen(cmd, stdout=devnull, shell=True)

            for duration in self._profile_duration_seconds:
                # Collect perf data from debugd.
                for get_perf_method in get_perf_methods:
                    self.validate_get_perf_method(get_perf_method, duration,
                                                  profile_type)

            # Terminate the process and actually wait for it to terminate.
            process.terminate()
            while process.poll() == None:
                pass

        devnull.close()
