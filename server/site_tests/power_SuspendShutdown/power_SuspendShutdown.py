# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.server import test
from autotest_lib.server.cros.faft.config.config import Config as FAFTConfig
from autotest_lib.server.cros import pyauto_proxy

_RETRY_SUSPEND_ATTEMPTS = 1
_RETRY_SUSPEND_MS = 10000
_SUSPEND_WAIT_SECONDS = 30
_BOOT_WAIT_SECONDS = 100


class power_SuspendShutdown(test.test):
    """Test power manager fallback to power-off if suspend fails."""
    version = 1

    def initialize(self, host):
        # save original boot id
        self.orig_boot_id = host.get_boot_id()

        # override /sys/power/state via bind mount
        logging.info('binding /dev/full to /sys/power/state')
        host.run('mount --bind /dev/full /sys/power/state')

        # override suspend retry attempts via bind mount
        logging.info('settings retry_suspend_attempts to %s',
                     _RETRY_SUSPEND_ATTEMPTS)
        host.run('echo %s > /tmp/retry_suspend_attempts;'
                 ' mount --bind /tmp/retry_suspend_attempts'
                 ' /usr/share/power_manager/retry_suspend_attempts'
                 % _RETRY_SUSPEND_ATTEMPTS)

        # override suspend retry interval via bind mount
        logging.info('settings retry_suspend_ms to %s',
                     _RETRY_SUSPEND_MS)
        host.run('echo %s > /tmp/retry_suspend_ms;'
                 ' mount --bind /tmp/retry_suspend_ms'
                 ' /usr/share/power_manager/retry_suspend_ms'
                 % _RETRY_SUSPEND_MS)

        # restart powerd to pick up new retry settings
        logging.info('restarting powerd')
        host.run('restart powerd')

        # initialize pyauto
        self.pyauto = pyauto_proxy.create_pyauto_proxy(host, auto_login=True)


    def platform_check(self, platform_name):
        client_attr = FAFTConfig(platform_name)

        if not client_attr.has_lid:
            raise error.TestError(
                    'This test does nothing on devices without a lid.')

        if client_attr.chrome_ec and not 'lid' in client_attr.ec_capability:
            raise error.TestNAError("TEST IT MANUALLY! Chrome EC can't control "
                    "lid on the device %s" % client_attr.platform)


    def run_once(self, host=None):
        # check platform is capable of running the test
        platform = host.run_output('mosys platform name')
        logging.info('platform is %s', platform)
        self.platform_check(platform)

        # close the lid to initiate suspend
        logging.info('closing lid')
        host.servo.lid_close()

        # wait for power manager to give up and shut down
        logging.info('waiting for power off')
        host.wait_down(timeout=_SUSPEND_WAIT_SECONDS,
                       old_boot_id=self.orig_boot_id)

        # ensure host is now off
        if host.is_up():
            raise error.TestFail('DUT still up with lid closed')
        else:
            logging.info('good, host is now off')

        # restart host
        host.servo.lid_open()
        host.wait_up(timeout=_BOOT_WAIT_SECONDS)


    def cleanup(self, host):
        # reopen lid - might still be closed due to failure
        logging.info('reopening lid')
        host.servo.lid_open()

        # try to clean up the mess we've made if shutdown failed
        if host.get_boot_id() == self.orig_boot_id:
            # clean up mounts
            logging.info('cleaning up bind mounts')
            host.run('umount /sys/power/state'
                     ' /usr/share/power_manager/retry_suspend_attempts'
                     ' /usr/share/power_manager/retry_suspend_ms',
                     ignore_status=True)

            # restart powerd to pick up old retry settings
            host.run('restart powerd')

            # cleanup pyauto
            self.pyauto.cleanup()
