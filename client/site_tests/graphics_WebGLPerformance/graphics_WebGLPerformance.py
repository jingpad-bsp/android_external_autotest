# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, shutil, time, urllib
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui, cros_ui_test, graphics_ui_test
from autotest_lib.client.cros import httpd

class graphics_WebGLPerformance(graphics_ui_test.GraphicsUITest):
    version = 1

    def initialize(self, creds='$default'):
        self._test_url = 'http://localhost:8000/webgl-performance-tests.html'
        self._testServer = httpd.HTTPListener(8000, docroot=self.srcdir)
        self._testServer.run()
        graphics_ui_test.GraphicsUITest.initialize(self, creds,
                                       extra_chrome_flags=['--enable-webgl'])

    def setup(self, tarball='webgl-performance-0.0.1.tar.bz2'):
        shutil.rmtree(self.srcdir, ignore_errors=True)
        tarball_path = os.path.join(self.bindir, tarball)
        if not os.path.exists(self.srcdir):
            if not os.path.exists(tarball_path):
                utils.get_file(
                    'http://commondatastorage.googleapis.com/'
                    'chromeos-localmirror/distfiles/' + tarball,
                    tarball_path)
            os.mkdir(self.srcdir)
            utils.extract_tarball_to_dir(tarball_path, self.srcdir)
        os.chdir(self.srcdir)
        utils.system('patch -p2 < ../webgl-performance-0.0.1.patch')
        shutil.copy('../favicon.ico', self.srcdir)

    def cleanup(self):
        self._testServer.stop()
        graphics_ui_test.GraphicsUITest.cleanup(self)

    def run_once(self, timeout=600):
        # TODO(ihf): Remove when stable. For now we have to expect crashes.
        self.crash_blacklist.append('chrome')
        self.crash_blacklist.append('chromium')

        latch = self._testServer.add_wait_url('/WebGL/results')
        # Loading the url might take longer than pyauto automation timeout.
        # Temporarily increment pyauto timeout.
        pyauto_timeout_changer = self.pyauto.ActionTimeoutChanger(
            self.pyauto, timeout * 1000)
        logging.info('Going to %s' % self._test_url)
        # TODO(ihf): Use the pyauto perf mechanisms to calm the system down.
        utils.system('sync')
        time.sleep(10.0)
        self.pyauto.NavigateToURL(self._test_url)
        del pyauto_timeout_changer
        latch.wait(timeout)

        if not latch.is_set():
            raise error.TestFail('Timeout after ' + str(timeout) +
                  ' seconds - never received callback from browser.')

        # Receive data from webgl-performance-tests.html::postFinalResults.
        results = self._testServer.get_form_entries()
        time_ms_geom_mean = float(results['time_ms_geom_mean'])

        # Output numbers for plotting by harness.
        keyvals = {}
        keyvals['time_ms_geom_mean'] = time_ms_geom_mean
        logging.info('WebGLPerformance: time_ms_geom_mean = %f'\
                                      % time_ms_geom_mean)
        self.write_perf_keyval(keyvals)
        # TODO(ihf): Switch this test to Telemetry (in cros_ui_test.py) so that
        # the numbers actually make it to the perf dashboard.
        self.output_perf_value(description='time_geom_mean',
                               value=time_ms_geom_mean, units='ms',
                               higher_is_better=False)

        # Write transmitted summary to graphics_WebGLPerformance/summary.html.
        summary = urllib.unquote_plus(results['summary'])
        logging.info('\n' + summary)
        results_path = os.path.join(self.bindir,
              "../../results/default/graphics_WebGLPerformance/summary.html")
        f = open(results_path, 'w+')
        f.write(summary)
        f.close()
        # Allow somebody to take a look at the screen.
        time.sleep(10.0)

