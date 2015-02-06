# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.common_lib.cros import dbus_send

SERVICE_NAME = 'org.chromium.Buffet'

MANAGER_INTERFACE = 'org.chromium.Buffet.Manager'
MANAGER_OBJECT_PATH = '/org/chromium/Buffet/Manager'

TEST_MESSAGE = 'Hello world!'

class BuffetConfig(object):
    """An object that knows how to restart buffet in various configurations."""

    @staticmethod
    def naive_restart(host=None):
        """Restart Buffet without configuring it in any way.

        @param host: Host object if we're interested in a remote host.

        """
        run = utils.run if host is None else host.run
        run('stop buffet', ignore_status=True)
        run('start buffet')


    def restart_with_config(self, host=None, timeout_seconds=10):
        """Restart Buffet with this configuration.

        @param host: Host object if we're interested in a remote host.
        @param timeout_seconds: number of seconds to wait for Buffet to
                come up.

        """
        run = utils.run if host is None else host.run
        self.naive_restart(host=host)
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            result = dbus_send.dbus_send(
                    SERVICE_NAME, MANAGER_INTERFACE, MANAGER_OBJECT_PATH,
                    'TestMethod', args=[dbus.String(TEST_MESSAGE)],
                    host=host, tolerate_failures=True)
            if result and result.response == TEST_MESSAGE:
                return
            time.sleep(0.5)

        raise error.TestFail('Buffet failed to restart in time.')
