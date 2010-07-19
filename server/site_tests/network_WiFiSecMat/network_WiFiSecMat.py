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

import logging


class network_WiFiSecMat(test.test):
  version = 1

  def expect_failure(self, name, reason):
    if reason is None:
      reason = "no reason given"
    logging.info("%s: ignore failure (%s)", name, reason)


  # The testcase config, setup, etc are done out side the individual
  # test loop, in the control file.
  def run_once(self, testcase, config):
    name = testcase['name']
    try:
      if 'skip_test' in testcase:
        logging.info("%s: SKIP: %s", name, testcase['skip_test'])
      else:
        wt = site_wifitest.WiFiTest(name, testcase['steps'], config)
        wt.run()
        wt.write_keyvals(self)
    except error.TestFail:
      if 'expect_failure' in testcase:
	expect_failure(name, testcase['expect_failure'])
      else:
        raise
    except Exception, e:
      if 'expect_failure' in testcase:
	expect_failure(name, testcase['expect_failure'])
      else:
        raise error.TestFail(e)

