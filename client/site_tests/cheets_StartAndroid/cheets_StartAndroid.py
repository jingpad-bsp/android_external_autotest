# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import os.path
import time
from autotest_lib.client.common_lib.cros import arc
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.bin import test

class cheets_StartAndroid(test.test):
    """Helper to run Android's CTS on autotest.

    Android CTS needs a running Android, which depends on a logged in ChromeOS
    user. This helper class logs in to ChromeOS and waits for Android boot
    complete.

    We do not log out, and the machine will be rebooted after test.
    """
    version = 1

    def cleanup(self):
        """Log to the dashboard after everything finishes up"""
        if hasattr(self, '_run_times'):
            logging.debug("Times to start Chrome and Android: %s",
                          self._run_times)
            # Report the first, second and last start times to perf dashboard.
            for index in [0, 1, len(self._run_times) - 1]:
                if index >= len(self._run_times):
                    continue
                self.output_perf_value(
                    description='Time_to_Start_Chrome_and_Android-%d' % (
                        index + 1),
                    value=self._run_times[index],
                    units='seconds',
                    higher_is_better=False,
                    replace_existing_values=True,
                    graph="Time_to_start_Chrome_and_Android"
                )

    def run_once(self, count=None, dont_override_profile=False):
        """Run stress test by logging in and starting ARC several times."""
        if count:
            # Each iteration is about 15s on Samus.
            self._run_times = []
            for i in range(count):
                logging.info('cheets_StartAndroid iteration %d', i)

                try:
                    start = datetime.datetime.utcnow()
                    chrome_obj = chrome.Chrome(
                        arc_mode = arc.arc_common.ARC_MODE_ENABLED,
                        dont_override_profile=dont_override_profile)
                    elapsed_time = (datetime.datetime.utcnow() - start
                           ).total_seconds()
                    self._run_times.append(elapsed_time)

                except:
                    pid = chrome_obj.get_browser_pid()
                    chrome_comm = os.path.join('/proc/', str(pid), '/comm')
                    if os.path.isfile(chrome_comm):
                        with open(chrome_comm, 'r') as f:
                            if f.read() == 'chrome':
                                logging.info('Chrome is still alive')
                            else:
                                logging.info('This PID is no longer chrome')
                    else:
                        logging.info('Chrome seems to have died')

                # 2 seconds for chrome to settle down before logging out
                time.sleep(2)
                chrome_obj.close()

        else:
            # Utility used by server tests to login. We do not log out, and
            # ensure the machine will be rebooted after test.
            try:
                self.chrome = chrome.Chrome(
                            dont_override_profile=dont_override_profile,
                            arc_mode=arc.arc_common.ARC_MODE_ENABLED)
            except:
                # We are going to paper over some failures here. Notice these
                # should still be detected by regularly running
                # cheets_StartAndroid.stress.
                logging.error('Could not start Chrome. Retrying soon...')
                # Give system a chance to calm down.
                time.sleep(20)
                self.chrome = chrome.Chrome(
                            dont_override_profile=dont_override_profile,
                            arc_mode=arc.arc_common.ARC_MODE_ENABLED,
                            num_tries=3)
