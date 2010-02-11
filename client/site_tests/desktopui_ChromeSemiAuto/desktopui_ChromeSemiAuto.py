# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, site_httpd, site_ui, utils


class desktopui_ChromeSemiAuto(test.test):
    version = 1

    def initialize(self):
        self._test_url = 'http://localhost:8000/interaction.html'
        # TODO(seano): Use ephemeral port.
        self._testServer = site_httpd.HTTPListener(8000, docroot=self.bindir)
        self._testServer.run()


    def cleanup(self):
        self._testServer.stop()


    def run_once(self, timeout=60):
        latch = self._testServer.add_wait_url('/interaction/test')

        session = site_ui.ChromeSession(self._test_url)
        logging.debug('Chrome session started.')
        latch.wait(timeout)
        session.close()

        if not latch.is_set():
            raise error.TestFail('Timeout.')

        result = self._testServer.get_form_entries()['result']
        logging.info('result = ' + result)
        if result != 'pass':
            raise error.TestFail('User indicated test failure.')
