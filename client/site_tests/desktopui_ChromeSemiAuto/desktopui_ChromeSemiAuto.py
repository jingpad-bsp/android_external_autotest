# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, site_httpd


class desktopui_ChromeSemiAuto(test.test):
    version = 1

    def initialize(self):
        self._binary = '/opt/google/chrome/chrome'
        self._test_url = 'http://localhost:8000/interaction.html'
        # TODO(seano): Change to use browser session lib, vs. direct cmds.
        self._env = 'DISPLAY=:0.0 XAUTHORITY=/home/chronos/.Xauthority'
        self._command = ' '.join([self._env, self._binary, self._test_url])
        # TODO(seano): Use ephemeral port.
        self._testServer = site_httpd.HTTPListener(8000, docroot=self.bindir)
        self._testServer.run()


    def cleanup(self):
        self._testServer.stop()


    def run_once(self):
        latch = self._testServer.add_wait_url('/interaction/test')
        try:
            utils.system('su chronos -c \'%s\'' % self._command)
        except error.CmdError, e:
            logging.debug(e)
            raise error.TestFail('Login information missing')
        while not latch.is_set():
            latch.wait(5)
        result = self._testServer.get_form_entries()['result']
        logging.info('result = ' + result)
        if result != 'pass':
            raise error.TestFail('User indicated test failure.')
