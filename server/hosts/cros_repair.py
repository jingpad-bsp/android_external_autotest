# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

import common
from autotest_lib.client.common_lib import hosts
from autotest_lib.server.hosts import ssh_verify


class ACPowerVerifier(hosts.Verifier):
    """Check for AC power and a reasonable battery charge."""

    def verify(self, host):
        info = host.get_power_supply_info()
        try:
            if info['Line Power']['online'] != 'yes':
                raise hosts.AutotestHostVerifyError(
                        'AC power is not online')
        except KeyError:
            logging.info('Cannot determine AC power status - '
                         'skipping check.')
        try:
            if float(info['Battery']['percentage']) < 50.0:
                raise hosts.AutotestHostVerifyError(
                        'Battery is less than 50%')
        except KeyError:
            logging.info('Cannot determine battery status - '
                         'skipping check.')


    @property
    def description(self):
        return 'host is plugged in to AC power'


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
    return hosts.RepairStrategy((
            (ssh_verify.SshVerifier, 'ssh', []),
            (ACPowerVerifier, 'power', ['ssh']),
            (CrosHostVerifier, 'cros', ['ssh'])))
