# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, os.path, time
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.crash_test import CrashTest

class logging_CrashServices(test.test):
    version = 2

    process_list = [
        '/sbin/agetty',
        '/usr/sbin/cryptohomed',
        '/usr/bin/metrics_daemon',
        '/usr/bin/powerd',
        '/usr/sbin/rsyslogd',
        '/usr/sbin/tcsd',
        '/usr/bin/tlsdated',
        '/usr/bin/shill',
        '/usr/sbin/update_engine',
        '/usr/sbin/wpa_supplicant',
        '/usr/bin/X',
        #this will log out, so it's last
        '/sbin/session_manager'
    ]

    def _kill_processes(self, name):
        return utils.system("killall -w -s SEGV %s" % name, ignore_status=True)


    def _find_crash_files(self, extension):
        return self._find_file_in_path(CrashTest._SYSTEM_CRASH_DIR,
                                       extension) \
            or self._find_file_in_path(CrashTest._USER_CRASH_DIR, extension)


    def _find_file_in_path(self, path, filetype):
        try:
            entries = os.listdir(path)
        except OSError:
            return None

        for entry in entries:
            (_, ext) = os.path.splitext(entry)
            if ext == filetype:
                return entry
        return None


    def _test_process(self, process_path):
        if self._kill_processes(process_path):
            raise error.TestFail("Failed to kill process %s" % process_path)

        # wait for .core and .dmp and .meta files in a crash directory
        utils.poll_for_condition(
            condition=lambda: self._find_crash_files(".core"),
            desc="Waiting for .core for %s" % process_path)
        utils.poll_for_condition(
            condition=lambda: self._find_crash_files(".dmp"),
            desc="Waiting for .dmp for %s" % process_path)
        utils.poll_for_condition(
            condition=lambda: self._find_crash_files(".meta"),
            desc="Waiting for .meta for %s" % process_path)


    def run_once(self, process_path=None):
        if process_path:
            self._test_process(process_path)
            return

        with chrome.Chrome():
            for process_path in self.process_list:
                self.job.run_test("logging_CrashServices",
                                  process_path=process_path,
                                  tag=os.path.basename(process_path))

