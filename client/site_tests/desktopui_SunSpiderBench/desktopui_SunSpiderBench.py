# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, shutil
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error, site_httpd, site_ui


class desktopui_SunSpiderBench(test.test):
    version = 1

    def initialize(self):
        self._test_url = 'http://localhost:8000/sunspider-driver.html'
        self._testServer = site_httpd.HTTPListener(8000, docroot=self.srcdir)
        self._testServer.run()


    def setup(self, tarball = 'sunspider-0.9.tar.bz2'):
        shutil.rmtree(self.srcdir, ignore_errors=True)
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)
        utils.system('patch -p1 < ../sunspider.patch')


    def cleanup(self):
        self._testServer.stop()


    def run_once(self, timeout=180):
        latch = self._testServer.add_wait_url('/sunspider/scores')

        session = site_ui.ChromeSession(self._test_url)
        logging.debug('Chrome session started.')
        latch.wait(timeout)
        session.close()

        if not latch.is_set():
            raise error.TestFail('Never received callback from browser.')

        self.write_perf_keyval(self._testServer.get_form_entries())
