# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, shutil
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, httpd

class desktopui_SunSpiderBench(cros_ui_test.UITest):
    version = 1

    def initialize(self, creds='$default', **dargs):
        self._test_url = 'http://localhost:8000/sunspider-driver.html'
        self._testServer = httpd.HTTPListener(8000, docroot=self.srcdir)
        self._testServer.run()
        super(desktopui_SunSpiderBench, self).initialize(creds, **dargs)


    def setup(self, tarball='sunspider-0.9.tar.bz2'):
        shutil.rmtree(self.srcdir, ignore_errors=True)
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)
        utils.system('patch -p1 < ../sunspider.patch')


    def cleanup(self):
        self._testServer.stop()
        super(desktopui_SunSpiderBench, self).cleanup()


    def run_once(self, timeout=180):
        latch = self._testServer.add_wait_url('/sunspider/scores')

        # Temporarily increment pyauto timeout
        pyauto_timeout_changer = self.pyauto.ActionTimeoutChanger(
            self.pyauto, timeout * 1000)
        self.pyauto.NavigateToURL(self._test_url)
        del pyauto_timeout_changer
        latch.wait(timeout)

        if not latch.is_set():
            raise error.TestFail('Never received callback from browser.')

        self.write_perf_keyval(self._testServer.get_form_entries())
