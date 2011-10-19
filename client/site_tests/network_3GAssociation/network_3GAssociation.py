# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import flimflam_test_path
import flimflam


class network_3GAssociation(test.test):
    version = 1

    def ConnectTo3GNetwork(self, timeout):
        """Attempts to connect to a 3G network using FlimFlam.

        Args:
          timeout: Timeout (in seconds) before giving up operations.

        Raises:
          error.TestFail if connection fails.
        """
        logging.info('ConnectTo3GNetwork')

        success, status = self.flim.ConnectService(
            service=self.service,
            timeout=timeout)
        if not success:
            raise error.TestFail('Could not connect: %s.' % status)

        connected_states = ['ready', 'portal', 'online']
        state = self.flim.WaitForServiceState(service=self.service,
                                              expected_states=connected_states,
                                              timeout=timeout,
                                              ignore_failure=True)[0]
        if not state in connected_states:
            raise error.TestFail('Still in state %s' % state)

        return state

    def DisconnectFrom3GNetwork(self, disconnect_timeout):
        """Attempts to disconnect from a 3G network using FlimFlam.

        Args:
          disconnect_timeout: Wait this long (in seconds) for
              disconnect to take effect.

        Raises:
          error.TestFail if the disconnect operation times out.
        """
        logging.info('DisconnectFrom3GNetwork')

        success, status = self.flim.DisconnectService(
            service=self.service,
            wait_timeout=disconnect_timeout)
        if not success:
            raise error.TestFail('Could not disconnect: %s.' % status)

    def run_once(self, connect_count=10, maximum_avg_assoc_time_seconds=5):
        # no backchannel required because we are just testing the time
        # to make a network connection.  The wired ethernet can be
        # left with the default route.
        self.flim = flimflam.FlimFlam()
        self.service = self.flim.FindCellularService()
        self.DisconnectFrom3GNetwork(disconnect_timeout=20)

        total_time_seconds = 0.0
        for _ in xrange(connect_count):
            start_time_seconds = time.time()
            state = self.ConnectTo3GNetwork(timeout=20)
            assoc_time_seconds = time.time() - start_time_seconds
            self.write_perf_keyval(
                {'seconds_3G_assoc_time': assoc_time_seconds })
            self.DisconnectFrom3GNetwork(disconnect_timeout=20)
            total_time_seconds += assoc_time_seconds

        average_assoc_time_seconds = total_time_seconds / connect_count
        self.write_perf_keyval(
                {'average_seconds_3G_assoc_time': average_assoc_time_seconds})
        if average_assoc_time_seconds > maximum_avg_assoc_time_seconds:
            raise error.TestFail(
                'Average association time %s is greater than %s' % (
                    average_assoc_time_seconds, maximum_avg_assoc_time_seconds))
