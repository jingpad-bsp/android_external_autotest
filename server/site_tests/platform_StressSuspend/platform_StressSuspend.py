# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json, time

from autotest_lib.server import autotest, test
from autotest_lib.server.cros import stress


_TIME_TO_SUSPEND = 10
_EXTRA_DELAY = 10


class platform_StressSuspend(test.test):
    """Uses servo to repeatedly close & open lid while running BrowserTests."""
    version = 1


    def run_once(self, host, client_autotest):
        autotest_client = autotest.Autotest(host)

        def sleepwake():
            """Close and open the lid with enough delay to induce suspend."""
            host.servo.lid_close()
            time.sleep(_TIME_TO_SUSPEND + _EXTRA_DELAY)
            host.servo.lid_open()
            time.sleep(_EXTRA_DELAY)

        def loggedin():
            """
            Checks if the host has a logged in user.

            @return True if a user is logged in on the device.
            """
            cmd_out = host.run('cryptohome --action=status').stdout.strip()
            status = json.loads(cmd_out)
            return any((mount['mounted'] for mount in status['mounts']))

        stressor = stress.ControlledStressor(sleepwake)
        stressor.start(start_condition=loggedin)
        autotest_client.run_test(client_autotest)
        stressor.stop()
