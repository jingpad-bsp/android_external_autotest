# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import common

from autotest_lib.client.common_lib import error
from autotest_lib.server.hosts import cros_host

class MoblabHost(cros_host.CrosHost):
    """Moblab specific host class."""


    @staticmethod
    def check_host(host, timeout=10):
        """
        Check if the given host is an moblab host.

        @param host: An ssh host representing a device.
        @param timeout: The timeout for the run command.


        @return: True if the host device has adb.

        @raises AutoservRunError: If the command failed.
        @raises AutoservSSHTimeout: Ssh connection has timed out.
        """
        try:
            result = host.run('grep -q moblab /etc/lsb-release',
                              ignore_status=True, timeout=timeout)
        except (error.AutoservRunError, error.AutoservSSHTimeout):
            return False
        return result.exit_status == 0


    def get_autodir(self):
        """Return the directory to install autotest for client side tests."""
        return '/tmp/autotest'
