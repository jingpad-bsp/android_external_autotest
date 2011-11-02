# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui, cros_ui_test, httpd

class desktopui_ChromeSemiAuto(cros_ui_test.UITest):
    version = 1

    def initialize(self, creds='$default', **dargs):
        self._test_url = 'http://localhost:8000/interaction.html'
        # TODO(seano): Use ephemeral port.
        self._testServer = httpd.HTTPListener(8000, docroot=self.bindir)
        self._testServer.run()
        super(desktopui_ChromeSemiAuto, self).initialize(creds, **dargs)


    def cleanup(self):
        self._testServer.stop()
        super(desktopui_ChromeSemiAuto, self).cleanup()


    def run_once(self, timeout=60):
        latch = self._testServer.add_wait_url('/interaction/test')

        # Temporarily increment pyauto timeout
        pyauto_timeout_changer = self.pyauto.ActionTimeoutChanger(
            self.pyauto, timeout * 1000)
        self.pyauto.NavigateToURL(self._test_url)
        del pyauto_timeout_changer
        latch.wait(timeout)

        if not latch.is_set():
            raise error.TestFail('Timeout.')

        result = self._testServer.get_form_entries()['result']
        logging.info('result = ' + result)
        if result != 'pass':
            raise error.TestFail('User indicated test failure.')
