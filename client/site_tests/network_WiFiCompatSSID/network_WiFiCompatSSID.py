# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_logging, cros_ui_test


class network_WiFiCompatSSID(cros_ui_test.UITest):
    version = 1

    def initialize(self):
        super(network_WiFiCompatSSID, self).initialize(creds='$default')

    def setup(self):
        super(network_WiFiCompatSSID, self).setup()
        self.pyauto.RunSuperuserActionOnChromeOS('CleanFlimflamDir')

    def _print_failure_messages_set_state(self, state, message):
        self.job.set_state('client_passed', state)
        logging.debug(message)
        if not state:
            raise error.TestFail(message)

    def _search_for_ssid(self, ssid, return_if_exist=True):
        # With as quickly as we are switching the environment it may take a
        # scan or two to pick up all of the changes.
        for i in range(3):
            wifi_networks = self.pyauto.NetworkScan()['wifi_networks']
            for key, val in wifi_networks.iteritems():
                if val['name'] == ssid and return_if_exist:
                    return key
            if not return_if_exist:
                return None
        return None

    def run_once(self, ssid=None, ssid_visible=True):
        if not ssid:
            self.job.set_state('client_passed', False)
            raise error.TestFail('The ssid was not set; test cannot continue.')
            return

        # Forget all remembered networks
        # TODO: Remove when https://chromiumcodereview.appspot.com/10119028/ is
        # upreved and replaced with:
        # self.pyauto.ForgetAllRememberedNetworks()
        for service in self.pyauto.GetNetworkInfo()['remembered_wifi']:
            self.pyauto.ForgetWifiNetwork(service)

        logging.debug('Running in mode visibility=%s' % ssid_visible)
        # logging.debug('All available networks: %s' % wifi_networks)

        if ssid_visible:
            device_path = self._search_for_ssid(ssid)
            if not device_path:
                msg = 'Unable to locate the visible ssid %s.' % ssid
                self._print_failure_messages_set_state(False, msg)
                return
            err = self.pyauto.ConnectToWifiNetwork(device_path)
            if err:
                msg = ('Failed to connect to wifi network %s. Reason: %s.'
                       % (ssid, err))
                self._print_failure_messages_set_state(False, msg)
                return
            else:
                msg = 'PASS: connected to network ssid=%s.' % ssid
                self._print_failure_messages_set_state(True, msg)
                self.pyauto.DisconnectFromWifiNetwork()
                return
        device_path = self._search_for_ssid(ssid, return_if_exist=False)
        if device_path:
            msg = 'Was able to see the invisible ssid %s.' % ssid
            self._print_failure_messages_set_state(False, msg)
            return
        err = self.pyauto.ConnectToHiddenWifiNetwork(ssid, 'SECURITY_NONE')
        if err:
            msg = ('Failed to connect to wifi network %s. Reason: %s.' %
                   (ssid, err))
            self._print_failure_messages_set_state(False, msg)
        else:
            msg = 'PASS: connected to hidden network with ssid=%s.' % ssid
            self._print_failure_messages_set_state(True, msg)
            self.pyauto.DisconnectFromWifiNetwork()
