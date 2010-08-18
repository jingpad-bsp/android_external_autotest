# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, shutil, time
from autotest_lib.client.common_lib import error
from autotest_lib.server import autotest, site_host_attributes, test


class logging_KernelCrashServer(test.test):
    version = 1


    def run_once(self, host=None):
        client_at = autotest.Autotest(host)
        client_at.run_test('logging_KernelCrash',
                           tag='before-crash',
                           is_before=True)

        client_attributes = site_host_attributes.HostAttributes(host.hostname)
        if not client_attributes.has_working_kcrash:
            raise error.TestNAError(
                'This device is unable to report kernel crashes')
        # Crash the client
        logging.info('KernelCrashServer: crashing %s' % host.hostname)
        boot_id = host.get_boot_id()
        host.run('sh -c "sleep 1; echo bug > /proc/breakme" >/dev/null 2>&1 &')
        host.wait_for_restart(old_boot_id=boot_id)

        # Check for crash handling
        client_at.run_test('logging_KernelCrash',
                           tag='after-crash',
                           is_before=False)
