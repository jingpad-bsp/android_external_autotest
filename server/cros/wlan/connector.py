# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, re, os

import common

from autotest_lib.client.common_lib.cros.site_wlan import constants
from autotest_lib.server.cros.wlan import api_shim


class ConnectException(Exception):
    """Base class for connection exceptions."""
    pass


class ConnectFailed(Exception):
    """Raised when a call to tell the DUT to connect fails."""
    pass


class ConnectTimeout(Exception):
    """Raised when a call to tell the DUT to connect takes too long."""
    pass


class Connector(api_shim.ApiShim):
    """Enables remotely ordering a DUT to connect to wifi.

    Currently implemented in terms of scripts in
    client/common_lib/cros/site_wlan.  This API should evolve together
    with the refactor of those scripts to provide an RPC interface to
    drive connectivity on DUTs: http://crosbug.com/35757
    """
    def __init__(self, host):
        super(Connector, self).__init__(host)


    @classmethod
    def _script_name(cls):
        """Returns the name of the script this class wraps."""
        return 'site_wlan_connect.py'


    def connect(self, ssid, security='', psk=''):
        """Attempts to connect client to AP.

        @param ssid: String formatted ssid.
        @param security: One of '', 'wep', 'psk'.
        @param psk: The passphrase if security is not ''.

        @raises ValueError if psk does not accompany non-'' value for security.
        @raises ConnectFailed upon failure.
        @raises ConnectTimeout if attempt takes more time than is allotted.

        @raises AutoservRunError: if the wrapped command failed.
        @raises AutoservSSHTimeout: ssh connection has timed out.
        """
        if security and not psk:
            raise ValueError('Passing security=%s requires a value for psk.')
        result = self._client.run('python "%s" "%s" "%s" "%s" "%d" "%d" '
                                  '--hidden' %
                                  (self._script,
                                   ssid, security, psk,
                                   constants.DEFAULT_TIMEOUT_SECONDS,
                                   constants.DEFAULT_TIMEOUT_SECONDS),
                                  ignore_status=True)
        # These codes are taken from main() in site_wlan_connect.py.
        if result.exit_status == 2:
            raise ConnectFailed(result.stdout)
        elif result.exit_status == 3:
            raise ConnectTimeout(result.stdout)
