# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os 
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error, site_httpd, site_ui


class desktopui_V8Bench(test.test):
    version = 1

    def initialize(self):
        self._test_url = 'http://localhost:8000/src/V8.html'
        self._testServer = site_httpd.HTTPListener(8000, docroot=self.bindir)
        self._testServer.run()


    def setup(self, tarball = 'V8.tar.bz2'):
        # clean
        if os.path.exists(self.srcdir):
          utils.system('rm -rf %s' % self.srcdir)

        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)


    def cleanup(self):
        self._testServer.stop()


    def run_once(self, timeout = 20):
        latch = self._testServer.add_wait_url('/V8Load/test')

        session = site_ui.ChromeSession(self._test_url)
        logging.debug('Chrome session started.')
        latch.wait(timeout)
        session.close()

        if not latch.is_set():
            raise error.TestFail('Never received callback from browser.')

        self.write_perf_keyval(self._testServer.get_form_entries())
