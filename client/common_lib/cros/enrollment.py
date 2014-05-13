# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os

from autotest_lib.client.bin import utils
from autotest_lib.client.cros import cros_ui, cryptohome, ownership
from telemetry.core import exceptions
from telemetry.core.backends.chrome import cros_interface


_PASSWD_FILE = '/var/tmp/tpm_passwd'


def ClearTPM():
    """Clears the TPM (if it is owned) using the password stored in
    /var/tmp/tpm_passwd. Returns True if tpm was owned.

    @return True if the TPM was owned - enrollment should not be attempted.
    """
    status = cryptohome.get_tpm_status()
    if not status['Owned']:
        logging.debug('TPM is not owned')
        return False
    password = status['Password']
    if not password:
        if not os.path.isfile(_PASSWD_FILE):
            logging.warn('Password file %s doesn\'t exist, cannot clear TPM. '
                         'You need to have the firmware clear the TPM, for '
                         'instance using crossystem or by toggling the dev '
                         'switch.', _PASSWD_FILE)
            return True
        with open(_PASSWD_FILE) as f:
            password = f.read().rstrip()

    if not password:
        logging.warn('Password file %s empty, cannot clear TPM. '
                     'You need to have the firmware clear the TPM, for '
                     'instance using crossystem or by toggling the dev switch.',
                     _PASSWD_FILE)
        return True

    cros_ui.stop()
    res = utils.system_output('tpm_clear --pass ' + password)
    logging.warn(repr(res))

    cryptohome.remove_all_vaults()
    ownership.clear_ownership_files_no_restart()
    logging.warn('Please reboot the system')
    return True


def _SaveTPMPassword():
    """Save TPM Password to /var/tpm/tpm_passwd.

    During enrollment, the TPM password becomes visible - we capture it and
    save it in to a local file, so we can clear the TPM at the end of the test.
    """
    password = utils.poll_for_condition(
            lambda: cryptohome.get_tpm_status()['Password'],
            sleep_interval=0.5, timeout=60)
    if password:
        with open(_PASSWD_FILE, 'w') as f:
            f.write(password)
    else:
        logging.warn('Could not save TPM password')
    logging.info('TPM Password: ' + password)
    return password


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
    _SaveTPMPassword()


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
