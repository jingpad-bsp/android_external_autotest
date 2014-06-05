# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib.cros import tpm_utils
from telemetry.core import exceptions
from telemetry.core.backends.chrome import cros_interface


def _ExecuteOobeCmd(browser, cmd):
    logging.info('Invoking ' + cmd)
    oobe = browser.oobe
    oobe.WaitForJavaScriptExpression('typeof Oobe !== \'undefined\'', 10)
    oobe.ExecuteJavaScript(cmd)


def SwitchToRemora(browser):
    """Switch to Remora enrollment.

    @param browser: telemetry browser object.
    """
    _cri = cros_interface.CrOSInterface()
    pid = _cri.GetChromePid()
    try:
        # This will restart the browser.
        _ExecuteOobeCmd(browser, 'Oobe.remoraRequisitionForTesting();')
    except (exceptions.BrowserConnectionGoneException,
            exceptions.TabCrashException):
        pass
    utils.poll_for_condition(lambda: pid != _cri.GetChromePid(), timeout=60)
    utils.poll_for_condition(lambda: browser.oobe_exists, timeout=30)

    _ExecuteOobeCmd(browser, 'Oobe.skipToLoginForTesting();')
    tpm_utils.SaveTPMPassword()


def FinishEnrollment(oobe):
    """Wait for enrollment to finish and dismiss the last enrollment screen.

    @param oobe: telemetry oobe object.
    """
    oobe.WaitForJavaScriptExpression(
            "document.getElementById('oauth-enrollment').className."
            "search('oauth-enroll-state-success') != -1", 30)
    oobe.EvaluateJavaScript('Oobe.enterpriseEnrollmentDone();')


def RemoraEnrollment(browser, user_id, password):
    """Enterprise login for a Remora device.

    @param browser: telemetry browser object.
    @param user_id: login credentials user_id.
    @param password: login credentials password.
    """
    SwitchToRemora(browser)
    browser.oobe.NavigateGaiaLogin(user_id, password)
    FinishEnrollment(browser.oobe)
