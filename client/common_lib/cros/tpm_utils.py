# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cryptohome


_PASSWD_FILE = '/var/tmp/tpm_password'


class NoTPMPasswordException(Exception):
    """No TPM Password could be found."""
    pass


def TPMStatus(client):
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


def IsTPMAvailable(client):
    """Returns True if the TPM is unowned and enabled.

    @param client: client object to run commands on.
    """
    status = TPMStatus(client)
    return status['Enabled'] and not status['Owned']


def ClearTPMServer(client, out_dir):
    """Clears the TPM and reboots from a server-side autotest.

    @param client: client object to run commands on.
    @param out_dir: temporary directory to store the retrieved password file.
    """
    if IsTPMAvailable(client):
        logging.debug('TPM is not owned')
        return

    client.run('stop ui')
    try:
        password = TPMStatus(client)['Password']
        if not password:
            try:
                client.get_file(_PASSWD_FILE, out_dir)
            except error.AutoservRunError:
                raise NoTPMPasswordException(
                        'TPM Password file %s doesn\'t exist, falling back on '
                        'clear_tpm_owner_request to clear the TPM. You may '
                        'need to have the firmware clear the TPM, for instance '
                        'by toggling the dev switch.' % _PASSWD_FILE)
            with open(os.path.join(out_dir,
                      os.path.basename(_PASSWD_FILE))) as f:
                password = f.read().rstrip()
        if not password:
            raise NoTPMPasswordException(
                    'TPM Password file %s empty, falling back on '
                    'clear_tpm_owner_request to clear the TPM. You may need to '
                    'have the firmware clear the TPM, for instance by toggling '
                    'the dev switch.' % _PASSWD_FILE)

        res = client.run('tpm_clear --pass ' + password).stdout.strip()
        logging.warn(repr(res))
    except NoTPMPasswordException as e:
        logging.warn(e.args[0])
        client.run('crossystem clear_tpm_owner_request=1')

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
