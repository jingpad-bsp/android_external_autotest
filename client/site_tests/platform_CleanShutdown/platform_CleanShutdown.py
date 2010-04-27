# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, time
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class platform_CleanShutdown(test.test):
    version = 1


    def _log_remove_if_exists(self, filename, message):
        if not os.path.exists(filename):
            return

        contents = utils.read_file(filename)
        logging.error('Last shutdown problem: %s. Detailed output was:\n%s' %
                      (message, contents))
        os.remove(filename)
        self._errors.append(message)


    def run_once(self):
        self._errors = []
        # Problems during shutdown are brought out in /var/log files
        # which we show here.
        self._log_remove_if_exists('/var/log/shutdown_cryptohome_umount_failure',
                                   'cryptohome unmount failed')
        self._log_remove_if_exists('/var/log/shutdown_stateful_umount_failure',
                                   'stateful unmount failed')
        self._log_remove_if_exists('/var/log/shutdown_force_kill_processes',
                                   'force killed processes')
        if self._errors:
            raise error.TestFail(
                'Last shutdown problems: %s' % ' and '.join(self._errors))
