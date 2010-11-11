# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import logging, re, time
from autotest_lib.client.bin import test, utils, site_log_reader
from autotest_lib.client.common_lib import error, site_ui

class desktopui_FlashSanityCheck(test.test):
    version = 1


    def run_once(self, time_to_wait=25):
        # take a snapshot from /var/log/messages.
        self._log_reader = site_log_reader.LogReader()
        self._log_reader.set_start_by_current()

        # open browser to youtube.com.
        session = site_ui.ChromeSession('http://www.youtube.com')
        # wait some time till the webpage got fully loaded.
        time.sleep(time_to_wait)
        session.close()
        # Question: do we need to test with other popular flash websites?

        # any better pattern matching?
        if self._log_reader.can_find(' Received crash notification for '):
            # well, there is a crash. sample crash message:
            # 2010-10-04T19:13:17.923673-07:00 localhost crash_reporter[30712]:
            # Received crash notification for chrome[29888] sig 11 (ignoring)
            raise error.TestFail('Browser crashed during test.\nMessage '
                                 'from /var/log/messages:\n%s' % new_msg)
