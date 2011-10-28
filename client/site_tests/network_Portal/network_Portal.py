# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import backchannel
from autotest_lib.client.cros.cellular import cell_tools
from autotest_lib.client.cros import flimflam_test_path
import flimflam

class network_Portal(test.test):
    version = 1

    def GetConnectedService(self, service_name):
        service = self.flim.FindElementByNameSubstring('Service',
                                                       service_name)
        if service:
            properties = service.GetProperties(utf8_strings=True)
            state = properties['State']

            if state in ('online', 'portal', 'ready'):
                self.service = service
                return True

        return False

    def TestConnect(self, service_name, expected_state, timeout_seconds=30):
        """Connect to a service and verifies the portal state

        Args:
          service_name: substring to match against services
          expected_state: expected state of service after connecting

        Returns:
          True if the service is in the expected state
          False otherwise

        Raises:
          error.TestFail on non-recoverable failure
        """
        logging.info('TestConnect(%s, %s)' % (service_name, expected_state))

        self.service.Disconnect()
        state = self.flim.WaitForServiceState(
            service=self.service,
            expected_states=['idle', 'failure'],
            timeout=5)[0]

        self.service.Connect()
        state = self.flim.WaitForServiceState(
            service=self.service,
            expected_states=['portal', 'online', 'failure'],
            timeout=timeout_seconds)[0]

        if state != expected_state:
            logging.error('Service state should be %s but is %s' %
                          (expected_state, state))
            return False

        return True


    def run_once(self, force_portal, iterations=10):
        errors = 0
        service_name = 'wifi'
        if force_portal:
            # depends on getting a consistent IP address from DNS
            # depends on portal detection using www.google.com or
            # clients3.google.com
            hosts = ['clients3.google.com', 'www.google.com']
            expected_state = 'portal'
        else:
            hosts = []
            expected_state = 'online'

        with backchannel.Backchannel():
            # Immediately after the backchannel is setup there may be no
            # services.  Try for up to 10 seconds to find one
            self.flim = flimflam.FlimFlam()
            utils.poll_for_condition(
                lambda: self.GetConnectedService(service_name),
                error.TestFail(
                    'No service named "%s" available' % service_name))
            with cell_tools.BlackholeContext(hosts):
                for _ in range(iterations):
                    if not self.TestConnect(service_name, expected_state):
                        errors += 1

                if errors:
                    raise error.TestFail('%d failures to enter state %s ' % (
                        errors, expected_state))
