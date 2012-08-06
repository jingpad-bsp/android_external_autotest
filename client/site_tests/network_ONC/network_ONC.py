# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.;
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# This is not a stand alone test and is to be run in conjunction with
# network_ONCServer server side tests to pre-load the device with onc files
# using the pyauto libraries then verify a successuful connection to the network

import logging
import pprint
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import auth_server, cros_ui_test, pyauto_test

class network_ONC(cros_ui_test.UITest):
  version = 1
  auto_login = False

  def initialize(self):
    base_class = 'policy_base.PolicyTestBase'
    cros_ui_test.UITest.initialize(self, pyuitest_class=base_class)
    self.pyauto.Login('testacct@testacct.com', 'testacct')
    self.pyauto.RunSuperuserActionOnChromeOS('CleanFlimflamDirs')

  def ConnectToWifiNetwork(self, ssid, encryption=None):
    service_path = self.pyauto.GetServicePath(ssid)
    if not service_path:
      raise error.TestError('Could not find desired network with '
                            'ssid %s' % ssid)
    logging.debug('Connecting to service_path %s for ssid %s' %
                  (service_path, ssid))
    self.pyauto.ConnectToWifiNetwork(service_path)

  def test_simple_wifi_connect(self, ssid, onc):
    """This test sets the ONC policy, then attemps to
       successfully connect to the network defined by
       the ONC file."""

    logging.debug('Attempting to set onc file:\n%s' % onc)
    self.pyauto.SetUserPolicy({'OpenNetworkConfiguration': onc})

    self.ConnectToWifiNetwork(ssid)

    # Verify wifi network set by ONC is in the list
    network_list = self.pyauto.NetworkScan().get('wifi_networks')
    logging.debug('Scanned network list after connect.')
    logging.debug(pprint.pformat(network_list))
    for network_path, network_obj in network_list.iteritems():
      if network_obj['name'] == ssid and \
         network_obj['status'] in ['Connected', 'Online state', 'Portal state']:
        break
    else:
      raise error.TestFail('Failed to connect to network %s' % ssid)

  def run_once(self, test_type, **params):
      logging.info('client: Running client test %s', test_type)
      getattr(self, test_type)(**params)
