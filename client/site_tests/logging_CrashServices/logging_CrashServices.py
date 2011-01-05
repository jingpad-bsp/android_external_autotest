# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, os.path, signal, time
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import constants as chromeos_constants, login 
from autotest_lib.client.cros import crash_test

class logging_CrashServices(crash_test.CrashTest):
    version = 1

    process_list = ["/usr/sbin/acpid",
                    "/sbin/agetty",
                    "/usr/sbin/cashewd",
                    "/opt/google/chrome/chrome",
                    "/usr/bin/chromeos-wm",
                    "/usr/sbin/console-kit-daemon",
                    "/usr/sbin/cryptohomed",
                    "/usr/libexec/devkit-daemon",
                    "/usr/libexec/devkit-disks-daemon",
                    "/usr/libexec/devkit-power-daemon",
                    "/sbin/dhcpcd",
                    "/usr/sbin/flimflamd",
                    "/usr/sbin/htpdate",
                    "/usr/bin/metrics_daemon",
                    "/usr/sbin/pkcsslotd",
                    "/usr/bin/powerd",
                    "/usr/bin/powerm",
                    "/usr/bin/pulseaudio",
                    "/usr/sbin/rsyslogd",
                    "/usr/sbin/tcsd",
                    #"/sbin/udevd", # ignores all signals except INT, TERM, KILL
                    "/usr/sbin/update_engine",
                    "/sbin/wpa_supplicant",
                    "/usr/bin/X11/X",
                    # this will log out, so it's last
                    "/sbin/session_manager"]


    def _kill_processes(self, name):
        return utils.system("killall -w -s SEGV %s" % name, ignore_status=True)


    def _find_core(self):
        return self._find_file_in_path(self._SYSTEM_CRASH_DIR, ".core") \
            or self._find_file_in_path(self._USER_CRASH_DIR, ".core")


    def _find_dmp(self):
        return self._find_file_in_path(self._SYSTEM_CRASH_DIR, ".dmp") \
            or self._find_file_in_path(self._USER_CRASH_DIR, ".dmp")


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

        # wait for .core and .dmp files to appear in a crash directory
        utils.poll_for_condition(
            condition=lambda: self._find_core(),
            desc="Waiting for .core for %s" % process_path)
        utils.poll_for_condition(
            condition=lambda: self._find_dmp(),
            desc="Waiting for .dmp for %s" % process_path)

        # run crash_sender and watch for successful send in logs
        result = self._call_sender_one_crash(report=self._find_dmp())
        if not result["send_success"]:
            raise error.TestFail("Crash sending unsuccessful")
        if self._find_dmp():
            raise error.TestFail(".dmp files were not removed")


    def initialize(self):
        crash_test.CrashTest.initialize(self)
        self._reset_rate_limiting()
        self._clear_spooled_crashes()
        self._push_consent()
        self._set_consent(True)


    def cleanup(self):
        crash_test.CrashTest.cleanup(self)


    def run_once(self, process_path=None):
        if process_path:
            self._test_process(process_path)
            return

        # log in
        (username, password) = chromeos_constants.CREDENTIALS["$default"]
        login.attempt_login(username, password)

        # test processes
        for process_path in self.process_list:
            self.job.run_test("logging_CrashServices",
                              process_path=process_path,
                              tag=os.path.basename(process_path))

        # killing session manager logs out, so this will probably fail
        try:
            login.attempt_logout()
            pass
