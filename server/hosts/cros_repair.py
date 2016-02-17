# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import json

import common
from autotest_lib.client.common_lib import hosts
from autotest_lib.server.hosts import ssh_verify


class ACPowerVerifier(hosts.Verifier):
    """Check for AC power and a reasonable battery charge."""

    def verify(self, host):
        info = host.get_power_supply_info()
        try:
            if info['Line Power']['online'] != 'yes':
                raise hosts.AutoservVerifyError(
                        'AC power is not online')
        except KeyError:
            logging.info('Cannot determine AC power status - '
                         'skipping check.')
        try:
            if float(info['Battery']['percentage']) < 50.0:
                raise hosts.AutoservVerifyError(
                        'Battery is less than 50%')
        except KeyError:
            logging.info('Cannot determine battery status - '
                         'skipping check.')


    @property
    def description(self):
        return 'host is plugged in to AC power'


class TPMStatusVerifier(hosts.Verifier):
    """Verify that the host's TPM is in a good state."""

    def verify(self, host):
        # This cryptohome command emits status information in JSON format. It
        # looks something like this:
        # {
        #    "installattrs": {
        #       ...
        #    },
        #    "mounts": [ {
        #       ...
        #    } ],
        #    "tpm": {
        #       "being_owned": false,
        #       "can_connect": true,
        #       "can_decrypt": false,
        #       "can_encrypt": false,
        #       "can_load_srk": true,
        #       "can_load_srk_pubkey": true,
        #       "enabled": true,
        #       "has_context": true,
        #       "has_cryptohome_key": false,
        #       "has_key_handle": false,
        #       "last_error": 0,
        #       "owned": true
        #    }
        # }
        output = host.run('cryptohome --action=status').stdout.strip()
        try:
            status = json.loads(output)
        except ValueError:
            logging.info('Cannot determine the Crytohome valid status - '
                         'skipping check.')
            return
        try:
            tpm = status['tpm']
            if not tpm['enabled']:
                raise hosts.AutotestHostVerifyError(
                        'TPM is not enabled -- Hardware is not working.')
            if not tpm['can_connect']:
                raise hosts.AutotestHostVerifyError(
                        ('TPM connect failed -- '
                         'last_error=%d.' % tpm['last_error']))
            if (tpm['owned'] and not tpm['can_load_srk']):
                raise hosts.AutotestHostVerifyError(
                        'Cannot load the TPM SRK')
            if (tpm['can_load_srk'] and not tpm['can_load_srk_pubkey']):
                raise hosts.AutotestHostVerifyError(
                        'Cannot load the TPM SRC public key')
        except KeyError:
            logging.info('Cannot determine the Crytohome valid status - '
                         'skipping check.')


    @property
    def description(self):
        return 'The host\'s TPM is available and working'


class CrosHostVerifier(hosts.Verifier):
    """
    Ask a CrOS host to perform its own verification.

    This class exists as a temporary legacy during refactoring to
    provide access to code that hasn't yet been rewritten to use the new
    repair and verify framework.
    """

    def verify(self, host):
        host.verify_software()
        host.verify_hardware()


    @property
    def description(self):
        return 'Miscellaneous CrOS host verification checks'


def create_repair_strategy():
    """Return a `RepairStrategy` for a `CrosHost`."""
    verify_dag = [
        (ssh_verify.SshVerifier,  'ssh',     []),
        (ACPowerVerifier,         'power',   ['ssh']),
        (TPMStatusVerifier,       'tpm',     ['ssh']),
        (CrosHostVerifier,        'cros',    ['ssh']),
    ]
    return hosts.RepairStrategy(verify_dag, [])
