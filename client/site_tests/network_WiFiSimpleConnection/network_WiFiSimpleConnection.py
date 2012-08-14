# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, urllib

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, wifi_simple_connector


class network_WiFiSimpleConnection(cros_ui_test.UITest):
    version = 1


    def initialize(self):
        super(network_WiFiSimpleConnection, self).initialize(creds='$default')


    def setup(self):
        super(network_WiFiSimpleConnection, self).setup()
        self.pyauto.RunSuperuserActionOnChromeOS('CleanFlimflamDir')


    def start_authserver(self):
        # We want to be able to get to the real internet.
        pass


    def _print_failure_messages_set_state(self, state, message):
        self.job.set_state('client_passed', state)
        logging.debug(message)
        if not state:
            raise error.TestFail(message)


    def run_once(self, ssid=None, ssid_visible=True,
                 wifi_security='SECURITY_NONE', wifi_password=''):
        self.job.set_state('client_passed', False)
        connector = wifi_simple_connector.WifiSimpleConnector(self.pyauto)
        connected = connector.connect_to_wifi_network(ssid=ssid,
            ssid_visible=ssid_visible, wifi_security=wifi_security,
            wifi_password=wifi_password)
        self.pyauto.NavigateToURL('http://www.msn.com')
        self.job.set_state('client_passed', True)
        logging.debug('Connection establish, client test exiting.')

