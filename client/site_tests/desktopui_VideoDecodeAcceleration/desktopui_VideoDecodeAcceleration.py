# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, httpd

WAIT_TIMEOUT_S = 10

class desktopui_VideoDecodeAcceleration(cros_ui_test.UITest):
    """This test verifies VDA works in Chrome."""
    version = 1

    def initialize(self):
        super(desktopui_VideoDecodeAcceleration, self).initialize('$default')
        self._testServer = httpd.HTTPListener(8000, docroot=self.bindir)
        self._testServer.run()


    def cleanup(self):
        if self._testServer:
            self._testServer.stop()
        super(desktopui_VideoDecodeAcceleration, self).cleanup()


    def run_once(self):
        """Tests whether VDA works by verifying histogram for the loaded video.
        """
        import pyauto

        self.pyauto.NavigateToURL('chrome://histograms/Media.Gpu')
        self.pyauto.AppendTab(pyauto.GURL('http://localhost:8000/video.mp4'))

        # Waiting for histogram updated for the test video.
        wait_time = 0 # seconds
        tab_contents = ''
        while 'Media.GpuVideoDecoderInitializeStatus' not in tab_contents:
            time.sleep(1)
            wait_time = wait_time + 1
            if wait_time > WAIT_TIMEOUT_S:
                raise error.TestError('Histogram gpu status failed to load.')
            self.pyauto.ReloadTab()
            tab_contents = self.pyauto.GetTabContents()

        self.pyauto.assertTrue('average = 0.0' in tab_contents,
                               msg='Video decode acceleration not working.')
