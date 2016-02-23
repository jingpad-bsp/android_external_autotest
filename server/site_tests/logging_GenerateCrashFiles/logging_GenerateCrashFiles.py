# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time, re

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.crash_test import CrashTest
from autotest_lib.server import test


class logging_GenerateCrashFiles(test.test):
    """Tests if crash files are generated when crash is invoked"""
    version = 1
    SHORT_WAIT = 3
    REBOOT_TIMEOUT = 60

    def check_crash_files(self, file_path, file_pattern_list):
        """Find if the crash dumps with appropriate extensions are created.
        @param file_path: path to the crash file directory
        @param file_pattern_list: patterns of matching crash files
        @returns missing_files list of missing files
        """
        missing_files = list()

        out = self.host.run('ls -la %s' % file_path, ignore_status=True)
        files_list = out.stdout.strip().split('\n')

        for file_pattern in file_pattern_list:
            has_match = False
            for crash_file in files_list:
                if re.match(file_pattern, crash_file) != None:
                    has_match = True
                    break
            if not has_match:
                missing_files.append(file_pattern)

        # Remove existing file crash files, if any.
        self.host.run('rm -f %s/*' % file_path, ignore_status=True)
        return missing_files

    def run_once(self, host, crash_cmd, crash_files):
        self.host = host

        # Sync the file system
        self.host.run('sync', ignore_status=True)
        time.sleep(self.SHORT_WAIT)

        # Execute crash command
        self.host.run(crash_cmd, ignore_status=True)
        logging.debug('Crash invoked!')

        # In case of kernel crash the reboot will take some time
        host.ping_wait_up(self.REBOOT_TIMEOUT)

        # Sync the file system
        self.host.run('sync', ignore_status=True)
        time.sleep(self.SHORT_WAIT)

        missing_files = self.check_crash_files(CrashTest._SYSTEM_CRASH_DIR,
                                               crash_files)
        if len(missing_files) > 0:
            raise error.TestFail('Crash files NOT generated: %s' %
                                  str(missing_files))

