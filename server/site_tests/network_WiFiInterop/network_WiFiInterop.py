# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

import common

from autotest_lib.client.common_lib import error
from autotest_lib.server import test
from autotest_lib.server.cros.wlan import connector, disconnector
from autotest_lib.server.cros.wlan import profile_manager

class network_WiFiInterop(test.test):
    version = 1


    def run_once(self, host, ssid='GoogleGuest', tries=1):
        c = connector.Connector(host)
        d = disconnector.Disconnector(host)

        d.disconnect(ssid)  # To be sure!
        with profile_manager.ProfileManager(host) as pm:
            for i in xrange(tries):
                try:
                    logging.info('Connect attempt %d', i)
                    c.connect(ssid)
                    pm.clear_global_profile()
                except connector.ConnectException as e:
                    raise error.TestFail(e)
                except error.CmdError as e:
                    raise error.TestError(e)
                finally:
                    d.disconnect(ssid)  # To be sure!
