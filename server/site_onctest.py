# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server import site_wifitest
from autotest_lib.server.cros import stress

class ONCTest(site_wifitest.WiFiTest):
    """ This class includes executing the ONC specific commands and is used
    in conjunction with WiFiTest for configuring the routers."""

    STATE_LIST  = {
        'STATE_LOGGED_IN': '/tmp/NETWORKONC_logged_in',
        'STATE_ONC_SET':'/tmp/NETWORKONC_onc_set',
        'STATE_EXIT':'/tmp/NETWORKONC_exit'
    }

    WAIT_FOR_CLIENT_TIMEOUT = 200

    def init_profile(self):
        # ONC type tests require chrome which seems to only like the default
        # profile.  For ONC tests, profile cleanup occurs when running
        # the client side test.
        pass


    def cleanup(self, params={}):
        self.client_logout()
        super(ONCTest, self).cleanup(params)


    def run_onc_client_test(self, params):
        if not params.get('test_type'):
          params['test_type'] = 'test_simple_set_user_onc'

        logging.info('Server: starting client test "%s"' % params['test_type'])
        self.client_at.run_test('network_ONC', **params)


    def set_user_onc(self, params):
        if not params.get('onc'):
            params['onc'] = ''

        params['test_type'] = 'test_simple_set_user_onc'

        # Start the thread that logs into chrome and sets the
        # device policy.
        self.client_test = stress.CountedStressor(
                                lambda: self.run_onc_client_test(params),
                                on_exit=lambda:self._client_logout())

        self.client_test.start(1)


    def _wait_for_client_state(self, state, timeout=WAIT_FOR_CLIENT_TIMEOUT):
        """ Waits till the client's state matches that of state.
        This is done via checking a series of state files the client
        writes to /tmp. """
        ending_time = time.time()+timeout
        while time.time() < ending_time:
            output = self.client.run('ls %s' % self.STATE_LIST[state],
                                     ignore_status=True)
            if output.exit_status == 0:
                break
            time.sleep(1)
        else:
            raise error.TestError('TIMEOUT waiting for ONC to be ready')


    def connect(self, params):
        """ Connect to the configured AP. """
        # Wait for the ONC configuration to be ready before connecting.
        self._wait_for_client_state('STATE_ONC_SET')
        super(ONCTest, self).connect(params)


    def _client_logout(self):
        # To end the client thread, it relies on state exit to be
        # present.
        self.client.run('touch %s' % self.STATE_LIST['STATE_EXIT'],
                        ignore_status=True)


    def client_logout(self, params=None):
        if not hasattr(self, 'client_test'):
            return

        self._client_logout()
        self.client_test.join(self.WAIT_FOR_CLIENT_TIMEOUT)
        self.client_test.reraise()
