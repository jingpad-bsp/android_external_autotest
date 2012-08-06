# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server import site_wifitest
import logging

class ONCTest(site_wifitest.WiFiTest):
  """ This class includes executing the ONC specific commands and is used
      in conjunction with WiFiTest for configuring the routers."""

  def init_profile(self):
    # ONC type tests require chrome which seems to only like the default
    # profile.  For ONC tests, profile cleanup occurs when running
    # the client side test.
    pass

  def run_onc_client_test(self, params):
    if not params.get('test_type'):
      params['test_type'] = 'test_simple_wifi_connect'

    if not params.get('ssid'):
      params['ssid'] = self.wifi.get_ssid()

    logging.info('Server: starting client test "%s"' % params['test_type'])
    self.client_at.run_test('network_ONC', **params)
