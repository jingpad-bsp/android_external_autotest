# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

import common
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.cellular import mm1_constants
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


def GetModemDisconnectWhileStateIsDisconnecting(family):
    """
    Returns a modem that fails on disconnect request.

    @param family: The family of the modem returned.
    @returns: A modem of the given family that fails disconnect.

    """
    modem_class = _GetModemSuperClass(family)
    class _TestModem(modem_class):
        """ Actual modem implementation. """
        @pm_utils.log_dbus_method(return_cb_arg='return_cb',
                                  raise_cb_arg='raise_cb')
        def Disconnect(
            self, bearer_path, return_cb, raise_cb, *return_cb_args):
            """
            Test implementation of
            org.freedesktop.ModemManager1.Modem.Simple.Disconnect. Sets the
            modem state to DISCONNECTING and then fails, fooling shill into
            thinking that the disconnect failed while disconnecting.

            Refer to modem_simple.ModemSimple.Connect for documentation.

            """
            # Proceed normally, if this Disconnect was initiated by a call
            # to Disable, which may happen due to auto-connect.
            if self.disable_step:
                modem_class.Disconnect(
                    self, bearer_path, return_cb, raise_cb, return_cb_args)
                return

            logging.info('Simulating failed Disconnect')
            self.ChangeState(mm1_constants.MM_MODEM_STATE_DISCONNECTING,
                             mm1_constants.MM_MODEM_STATE_CHANGE_REASON_UNKNOWN)
            time.sleep(5)
            raise pm_errors.MMCoreError(pm_errors.MMCoreError.FAILED)

    return _TestModem()


def GetModemDisconnectWhileDisconnectInProgress(family):
    """
    Returns a modem implementation that fails disconnect except the first one.

    @param family: The family of the returned modem.
    @returns: A modem of the given family that fails all but the first
            disconnect attempts.

    """
    modem_class = _GetModemSuperClass(family)
    class _TestModem(modem_class):
        """ The actual modem implementation. """
        def __init__(self):
            modem_class.__init__(self)
            self.disconnect_count = 0

        @pm_utils.log_dbus_method(return_cb_arg='return_cb',
                                  raise_cb_arg='raise_cb')
        def Disconnect(
            self, bearer_path, return_cb, raise_cb, *return_cb_args):
            """
            Test implementation of
            org.freedesktop.ModemManager1.Modem.Simple.Disconnect. Keeps
            count of successive disconnect operations and fails during all
            but the first one.

            Refer to modem_simple.ModemSimple.Connect for documentation.

            """
            # Proceed normally, if this Disconnect was initiated by a call
            # to Disable, which may happen due to auto-connect.
            if self.disable_step:
                modem_class.Disconnect(
                    self, bearer_path, return_cb, raise_cb, return_cb_args)
                return

            # On the first call, set the state to DISCONNECTING.
            self.disconnect_count += 1
            if self.disconnect_count == 1:
                self.ChangeState(
                        mm1_constants.MM_MODEM_STATE_DISCONNECTING,
                        mm1_constants.MM_MODEM_STATE_CHANGE_REASON_UNKNOWN)
                time.sleep(5)
            else:
                raise pm_errors.MMCoreError(pm_errors.MMCoreError.FAILED)

    return _TestModem()


def GetModemDisconnectFailOther(family):
    """
    Returns a modem that fails a disconnect attempt with a generic error.

    @param family: The family of the modem returned.
    @returns: A modem of the give family that fails disconnect.

    """
    modem_class = _GetModemSuperClass(family)
    class _TestModem(modem_class):
        """ The actual modem implementation. """
        @pm_utils.log_dbus_method(return_cb_arg='return_cb',
                                  raise_cb_arg='raise_cb')
        def Disconnect(
            self, bearer_path, return_cb, raise_cb, *return_cb_args):
            """
            Test implementation of
            org.freedesktop.ModemManager1.Modem.Simple.Disconnect.
            Fails with an error.

            Refer to modem_simple.ModemSimple.Connect for documentation.

            """
            # Proceed normally, if this Disconnect was initiated by a call
            # to Disable, which may happen due to auto-connect.
            if self.disable_step:
                modem_class.Disconnect(
                    self, bearer_path, return_cb, raise_cb, return_cb_args)
                return

            raise pm_errors.MMCoreError(pm_errors.MMCoreError.FAILED)

    return _TestModem()
