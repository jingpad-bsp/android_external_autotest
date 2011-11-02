# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import constants, cros_logging
from autotest_lib.client.cros import cros_ui_test, httpd


class desktopui_FlashSanityCheck(cros_ui_test.UITest):
    version = 3

    def initialize(self, **dargs):
        self._test_url = 'http://localhost:8000/index.html'
        self._testServer = httpd.HTTPListener(8000, docroot=self.srcdir)
        self._testServer.run()
        super(desktopui_FlashSanityCheck, self).initialize(**dargs)


    def run_once(self, time_to_wait=25):
        self._log_reader = cros_logging.LogReader()
        self._log_reader.set_start_by_current()

        # Ensure that the swf got pulled
        latch = self._testServer.add_wait_url('/Trivial.swf')
        self.pyauto.NavigateToURL(self._test_url)
        latch.wait(time_to_wait)

        child_processes = self.pyauto.GetBrowserInfo()['child_processes']
        flash_processes = [x for x in child_processes if
                           x['name'] == 'Shockwave Flash']
        if not flash_processes:
            raise error.TestFail('No flash process found.')

        # Any better pattern matching?
        msg = ' Received crash notification for ' + constants.BROWSER
        if self._log_reader.can_find(msg):
            raise error.TestFail('Browser crashed during test.')


    def cleanup(self):
        self._testServer.stop()
        super(desktopui_FlashSanityCheck, self).cleanup()
