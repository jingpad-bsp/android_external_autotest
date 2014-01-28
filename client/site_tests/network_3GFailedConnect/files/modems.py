# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

import common
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.cellular.pseudomodem import modem_3gpp
from autotest_lib.client.cros.cellular.pseudomodem import modem_cdma
from autotest_lib.client.cros.cellular.pseudomodem import pm_errors
from autotest_lib.client.cros.cellular.pseudomodem import utils as pm_utils

def _GetModemSuperClass(family):
    """
    Obtains the correct Modem base class to use for the given family.

    @param family: The modem family. Should be one of |3GPP|/|CDMA|.
    @returns: The relevant Modem base class.
    @raises error.TestError, if |family| is not one of '3GPP' or 'CDMA'.

    """
    if family == '3GPP':
        return modem_3gpp.Modem3gpp
    elif family == 'CDMA':
        return modem_cdma.ModemCdma
    else:
        raise error.TestError('Invalid pseudomodem family: %s', family)


def GetFailConnectModem(family):
    """
    Returns the correct modem subclass based on |family|.

    @param family: A string containing either '3GPP' or 'CDMA'.

    """
    modem_class = _GetModemSuperClass(family)

    class FailConnectModem(modem_class):
        """Custom fake Modem that always fails to connect."""
        @pm_utils.log_dbus_method(return_cb_arg='return_cb',
                                  raise_cb_arg='raise_cb')
        def Connect(self, properties, return_cb, raise_cb):
            logging.info('Connect call will fail.')
            raise_cb(pm_errors.MMCoreError(pm_errors.MMCoreError.FAILED))

    return FailConnectModem()
