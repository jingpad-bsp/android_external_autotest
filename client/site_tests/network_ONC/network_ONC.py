# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.;
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# This is not a stand alone test and is to be run in conjunction with
# network_ONCServer server side tests to pre-load the device with onc files
# using the pyauto libraries then verify a successuful connection to the network

import logging
import pprint
import os
import time
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import auth_server, cros_ui_test, pyauto_test

class network_ONC(cros_ui_test.UITest):
    version = 1
    auto_login = False

    STATE_LIST  = {
        'STATE_LOGGED_IN': '/tmp/NETWORKONC_logged_in',
        'STATE_ONC_SET':'/tmp/NETWORKONC_onc_set',
        'STATE_EXIT':'/tmp/NETWORKONC_exit'
    }

    TIMEOUT = 360

    def initialize(self):
        self._clear_states()
        base_class = 'policy_base.PolicyTestBase'
        cros_ui_test.UITest.initialize(self, pyuitest_class=base_class)
        self.pyauto.Login('user@example.com', 'password')
        self._set_state('STATE_LOGGED_IN')
        self.pyauto.RunSuperuserActionOnChromeOS('CleanFlimflamDirs')


    def cleanup(self):
        self._clear_states()
        super(network_ONC, self).cleanup()


    def _clear_states(self):
        """ Reset the state of the system by erasing all state files. """
        for state_key in self.STATE_LIST.keys():
            self._clear_state(state_key)


    def _clear_state(self, state):
        """ Erases the file repesenting the indicated state. """
        if state not in self.STATE_LIST:
            raise error.TestError('State \'%s\' not found.' % state)

        if os.path.isfile(self.STATE_LIST[state]):
            os.remove(self.STATE_LIST[state])


    def _set_state(self, state):
        """ Creates the file representing the state. """
        if state not in self.STATE_LIST:
            raise error.TestError('State \'%s\' not found.' % state)

        with open(self.STATE_LIST[state], 'w'):
            pass


    def wait_for_logout(self, test_timeout):
        """ Wait for logout file before exiting or if timeout is hit.

        Args:
            timeout: Integer representing the time to wait before
                     the loop terminates. 0 indicates no time limit.
        """

        end_time = time.time() + test_timeout

        # Break when the STATE_EXIT file exists, or we have
        # reached the timeout duration.
        while not os.path.isfile(self.STATE_LIST['STATE_EXIT']):

            # Only check the timout condition if test_timeout is not 0
            if test_timeout != 0 and time.time() > end_time:
                break

            time.sleep(1)

        logging.info('Exit flag detected or timeout reached, exiting.')


    def test_simple_set_user_onc(self, onc='', test_timeout=TIMEOUT):
        """ Set the user policy, waits for condition, then logs out.

        Args:
            onc: String representing the onc file.
            timeout: Time to wait before logging out.  0 if no limit.

        """
        self.pyauto.SetUserPolicy({'OpenNetworkConfiguration': onc})
        self._set_state('STATE_ONC_SET')
        self.wait_for_logout(test_timeout)


    def run_once(self, test_type, **params):
        logging.info('client: Running client test %s', test_type)
        getattr(self, test_type)(**params)
