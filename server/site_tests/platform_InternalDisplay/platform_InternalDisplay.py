# copyright (c) 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, threading

from autotest_lib.server import test
from autotest_lib.client.common_lib import error

_CHROME_PATH = '/opt/google/chrome/chrome'
_LONG_TIMEOUT = 120

class platform_InternalDisplay(test.test):
    version = 1


    def is_dut_chromebox(self):
        """check if the device type is chromebox

        @return true if it's chromebox

        """
        return self.host.run('cat /etc/lsb-release | grep DEVICETYPE=CHROMEBOX',
                             ignore_status=True).exit_status == 0

    def run_suspend(self):
        """Suspend i.e. powerd_dbus_suspend and wait

        @returns boot_id for the following resume

        """
        boot_id = self.host.get_boot_id()
        thread = threading.Thread(target = self.host.suspend)
        thread.start()
        self.host.test_wait_for_sleep(_LONG_TIMEOUT)
        return boot_id

    def run_once(self,host):

        self.host = host

        if self.is_dut_chromebox():
            raise error.TestNAError('DUT is Chromebox. Test Skipped')

        self.host.reboot()
        if self.host.has_internal_display() is not 'internal_display':
            raise error.TestFail('Internal display is missing after reboot.')

        boot_id = self.run_suspend()
        logging.info('DUT suspended')
        self.host.test_wait_for_resume(boot_id, _LONG_TIMEOUT)
        logging.info('DUT resumed')
        if self.host.has_internal_display() is not 'internal_display':
            raise error.TestFail('Internal display is missing after suspend & resume.')

