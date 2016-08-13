# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

import common
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib import site_utils
from autotest_lib.server import afe_utils
from autotest_lib.server import test
from autotest_lib.server.brillo import host_utils


_DEFAULT_PING_HOST = 'www.google.com'
_DEFAULT_PING_COUNT = 4
_DEFAULT_PING_TIMEOUT = 4


class brillo_PingTest(test.test):
    """Ping an Internet host."""
    version = 1

    def run_once(self, host=None, ssid=None, passphrase=None,
                 ping_host=_DEFAULT_PING_HOST,
                 ping_count=_DEFAULT_PING_COUNT,
                 ping_timeout=_DEFAULT_PING_TIMEOUT):
        """Pings an Internet host with given timeout and count values.

        @param host: A host object representing the DUT.
        @param ssid: Ssid to connect to.
        @param passphrase: A string representing the passphrase to the ssid.
        @param ping_host: The Internet host to ping.
        @param ping_count: The number of pings to attempt. The test passes if
                           we get at least one reply.
        @param ping_timeout: The number of seconds to wait for a reply.

        @raise TestFail: The test failed.
        """
        if afe_utils.host_in_lab(host):
            ssid = site_utils.get_wireless_ssid(host.hostname)
            passphrase = global_config.global_config.get_config_value(
                    'CLIENT', 'wireless_password', default=None)
        with host_utils.connect_to_ssid(host, ssid, passphrase):
            cmd = 'ping -q -c %s -W %s %s' % (ping_count, ping_timeout,
                                              ping_host)
            try:
                host.run(cmd)
            except error.GenericHostRunError:
                raise error.TestFail(
                        'Failed to ping %s in %d seconds on all %d attempts' %
                        (ping_host, ping_timeout, ping_count))
