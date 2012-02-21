# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.server import test, autotest


class desktopui_EnterprisePolicyServer(test.test):
    version = 1
    client_test = 'desktopui_EnterprisePolicy'
    client_at = None


    def reboot_client(self):
        logging.info('Server: rebooting client')
        self.client.reboot()


    def run_once(self, host=None, subtest=None, prod=False, enroll=False):
        """
        Args:
            subtest: Name of the test function to run.
            prod: Whether to point to production DMServer and gaia auth server.
            enroll: Whether the test enrolls the device.
        """
        # TODO(frankf): Remove once crosbug.com/26158 is fixed.
        enroll = True
        self.client = host
        self.client_at = autotest.Autotest(self.client)
        logging.info('Server: starting client test "%s"' % subtest)
        self.job.set_state('client_completed', False)
        self.client_at.run_test(self.client_test, subtest=subtest, prod=prod,
                                enroll=enroll)
        if enroll:
            self.reboot_client()

        if not self.job.get_state('client_completed'):
            raise error.TestFail('Server: client test failed.')
