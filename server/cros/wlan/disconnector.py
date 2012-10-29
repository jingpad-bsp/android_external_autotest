# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, re, os

import common

from autotest_lib.client.common_lib.cros.site_wlan import constants
from autotest_lib.server.cros.wlan import api_shim


class Disconnector(api_shim.ApiShim):
    """Enables remotely ordering a DUT to disconnect from wifi.

    Currently implemented in terms of scripts in
    client/common_lib/cros/site_wlan.  This API should evolve together
    with the refactor of those scripts to provide an RPC interface to
    drive connectivity on DUTs: http://crosbug.com/35757
    """
    def __init__(self, host):
        super(Disconnector, self).__init__(host)


    @classmethod
    def _script_name(cls):
        """Returns the name of the script this class wraps."""
        return 'site_wlan_disconnect.py'


    def disconnect(self, ssid):
        """Disconnects from requested SSID.

        Idempotent.  If not currently connected to ssid, that's fine.

        @param ssid: String formatted ssid.
        """
        output = self._client.run('python "%s" "%s" "%d"' %
                                  (self._script,
                                   ssid,
                                   constants.DEFAULT_TIMEOUT_SECONDS),
                                  ignore_status=True).stdout
        logging.debug('Disconnect status: %s', output)
