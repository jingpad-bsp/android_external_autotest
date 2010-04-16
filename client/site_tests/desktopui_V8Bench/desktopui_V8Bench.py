# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, shutil
from autotest_lib.client.bin import site_ui_test, utils
from autotest_lib.client.common_lib import error, site_httpd, site_ui


class desktopui_V8Bench(site_ui_test.UITest):
    version = 1

    def initialize(self, creds = '$default'):
        self._test_url = 'http://localhost:8000/run.html'
        self._testServer = site_httpd.HTTPListener(8000, docroot=self.srcdir)
        self._testServer.run()
        site_ui_test.UITest.initialize(self, creds)


    def setup(self, tarball='v8_v5.tar.bz2'):
        shutil.rmtree(self.srcdir, ignore_errors=True)
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)
        utils.system('patch -p1 < ../v8.patch')


    def cleanup(self):
        self._testServer.stop()
        site_ui_test.UITest.cleanup(self)


    def run_once(self, timeout=60):
        latch = self._testServer.add_wait_url('/v8/scores')

        session = site_ui.ChromeSession(self._test_url)
        logging.debug('Chrome session started.')
        latch.wait(timeout)
        session.close()

        if not latch.is_set():
            raise error.TestFail('Never received callback from browser.')

        self.write_perf_keyval(self._testServer.get_form_entries())
