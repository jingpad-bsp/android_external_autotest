# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cryptohome


_PASSWD_FILE = '/var/tmp/tpm_password'


def _TPMStatus(client):
    """Returns a dictionary with TPM status.

    @param client: client object to run commands on.
    """
    out = client.run('cryptohome --action=tpm_status').stdout.strip()
    out = out.replace('TPM ', '')
    lines = out.split('\n')
    status = {}
    for item in lines:
        item = item.split(':')
        if not item[0]:
            continue
        if len(item) == 1:
            item.append('')
        item = map(lambda x : x.strip(), item)
        item[1] = True if item[1] == 'true' else item[1]
        item[1] = False if item[1] == 'false' else item[1]
        status[item[0]] = item[1]
    return status


def ClearTPMServer(client, out_dir):
    """Clears the TPM and reboots from a server-side autotest.

    @param client: client object to run commands on.
    @param out_dir: temporary directory to store the retrieved password file.
    """
    status = _TPMStatus(client)
    if not status['Owned']:
        logging.debug('TPM is not owned')
        return
    password = status['Password']
    if not password:
        try:
            client.get_file(_PASSWD_FILE, out_dir)
        except error.AutoservRunError:
            logging.warn('Password file %s doesn\'t exist, cannot clear TPM. '
                         'You need to have the firmware clear the TPM, for '
                         'instance using crossystem or by toggling the dev '
                         'switch.', _PASSWD_FILE)
            return
        with open(os.path.join(out_dir, os.path.basename(_PASSWD_FILE))) as f:
            password = f.read().rstrip()
    if not password:
        logging.warn('Password file %s empty, cannot clear TPM. '
                     'You need to have the firmware clear the TPM, for '
                     'instance using crossystem or by toggling the dev switch.',
                     _PASSWD_FILE)
        return

    client.run('stop ui')
    res = client.run('tpm_clear --pass ' + password).stdout.strip()
    logging.warn(repr(res))

    client.run('rm -rf /home/.shadow/*')
    client.run('rm -rf /var/lib/whitelist/*')
    client.run('rm -f /home/chronos/Local\ State')
    client.reboot()


def SaveTPMPassword():
    """Save TPM Password to /var/tpm/tpm_password.

    The TPM password is visible until enrollment completes and the TPM is owned.
    We capture it and save it in to a local file, so we can clear the TPM at the
    end of the test.
    """
    if cryptohome.get_tpm_status()['Owned']:
        return

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
