# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from autotest_lib.client.cros import cros_ui_test, httpd


class desktopui_UrlStress(cros_ui_test.UITest):
    version = 1


    def initialize(self):
        super(desktopui_UrlStress, self).initialize(creds='$default')
        self._testServer = httpd.HTTPListener(8000, docroot=self.bindir)
        self._testServer.run()


    def run_once(self, length_seconds=300):
        start_time = time.time()
        while time.time() - start_time < length_seconds:
            self.pyauto.AppendTab('http://localhost:8000/hello.html')
            assert self.pyauto.GetActiveTabTitle() == 'Hello World'
            if self.pyauto.GetTabCount() > 25:
                while self.pyauto.GetTabCount() > 1:
                  self.pyauto.CloseTab()
