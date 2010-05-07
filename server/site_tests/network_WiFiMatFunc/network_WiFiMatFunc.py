# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""WiFiMatFunc is a suite of 3-machine tests to validate basic WiFi functionality.
One client, one server, and one programmable WiFi AP/Router are required
(either off-the-shelf with a network-accesible CLI or a Linux/BSD system
with a WiFi card that supports HostAP functionality).

Configuration information to run_test:

server     - the IP address of the server (automatically filled in)
client     - the IP address of the client (automatically filled in)
router     - the IP address of the WiFi AP/Router and the names of the
             wifi and wired devices to configure
"""


from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.server import autotest, site_wifitest, test


class network_WiFiMatFunc(test.test):
  version = 1

  # The testcase config, setup, etc are done out side the individual
  # test loop, in the control file.
  def run_once(self, testcase, config):
    try:
      wt = site_wifitest.WiFiTest(testcase['name'], testcase['steps'], config)
      wt.run()
    except error.TestFail:
      raise
    except Exception, e:
      raise error.TestFail(e)

