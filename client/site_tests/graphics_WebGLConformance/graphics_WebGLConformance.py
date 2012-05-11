# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, shutil, urllib
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui, cros_ui_test, graphics_ui_test
from autotest_lib.client.cros import httpd

class graphics_WebGLConformance(graphics_ui_test.GraphicsUITest):
    version = 2

    # TODO(ihf) not all tests are passing now, maintain this
    # list was assembled on mario but should be a superset
    # of all failing configurations
    waived_tests = {
          'conformance/constants.html' : 1,
          'conformance/context/constants.html' : 1,
          'conformance/context/context-attributes-alpha-depth-stencil-antialias.html' : 1,
          'conformance/context/premultiplyalpha-test.html' : 1,
          'conformance/extensions/oes-standard-derivatives.html' : 15,
          'conformance/gl-get-calls.html' : 1,
          'conformance/glsl/functions/glsl-function-acos.html' : 1,
          'conformance/glsl/functions/glsl-function-asin.html' : 1,
          'conformance/glsl/functions/glsl-function-atan.html' : 2,
          'conformance/glsl/functions/glsl-function-atan-xy.html' : 1,
          'conformance/glsl/functions/glsl-function-cos.html' : 4,
          'conformance/glsl/functions/glsl-function-sin.html' : 4,
          'conformance/glsl/functions/glsl-function-smoothstep-gentype.html' : 1,
          'conformance/glsl/variables/gl-frontfacing.html' : 16,
          # SNB only crosbug.com/27085:
          'conformance/glsl/variables/gl-pointcoord.html' : 48,
          'conformance/limits/gl-max-texture-dimensions.html' : 2,
          'conformance/misc/instanceof-test.html' : 1,
          'conformance/more/conformance/constants.html' : 1,
          'conformance/more/conformance/quickCheckAPI-B2.html' : 1,
          'conformance/more/conformance/quickCheckAPI-D_G.html' : 1,
          'conformance/more/conformance/quickCheckAPI-L_S.html' : 1,
          'conformance/more/functions/copyTexImage2D.html' : 1,
          'conformance/more/functions/readPixelsBadArgs.html' : 1,
          'conformance/more/functions/texImage2DHTML.html' : 1,
          'conformance/more/functions/texSubImage2DHTML.html' : 1,
          'conformance/rendering/line-loop-tri-fan.html' : 2,
          'conformance/rendering/point-size.html' : 3,
          'conformance/textures/origin-clean-conformance.html' : 4,
          # Alex but not mario or SNB:
          'conformance/textures/texture-formats-test.html' : 8,
          'conformance/textures/texture-mips.html' : 2,
          'conformance/textures/texture-npot.html' : 1,
          'conformance/textures/texture-size.html' : 6,
      }

    def initialize(self, creds='$default'):
        self._test_url = 'http://localhost:8000/webgl-conformance-tests.html'
        self._testServer = httpd.HTTPListener(8000, docroot=self.srcdir)
        self._testServer.run()
        graphics_ui_test.GraphicsUITest.initialize(self, creds,
                                       extra_chrome_flags=['--enable-webgl'])

    def setup(self, tarball='webgl-conformance-1.0.0-r2.tar.bz2'):
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
        utils.system('patch -p2 < ../webgl-conformance-1.0.0-r2.patch')
        shutil.copy('../favicon.ico', self.srcdir)

    def cleanup(self):
        self._testServer.stop()
        graphics_ui_test.GraphicsUITest.cleanup(self)

    def run_once(self, timeout=600):
        # TODO(ihf) remove when stable. for now we have to expect crashes
        self.crash_blacklist.append('chrome')
        self.crash_blacklist.append('chromium')
        self.crash_blacklist.append('supplied_chrome')

        latch = self._testServer.add_wait_url('/WebGL/results')
        # Loading the url might take longer than pyauto automation timeout.
        # Temporarily increment pyauto timeout.
        pyauto_timeout_changer = self.pyauto.ActionTimeoutChanger(
            self.pyauto, timeout * 1000)
        logging.info('Going to %s' % self._test_url)
        self.pyauto.NavigateToURL(self._test_url)
        del pyauto_timeout_changer
        latch.wait(timeout)

        if not latch.is_set():
            raise error.TestFail('Timeout after ' + str(timeout) +
                  ' seconds - never received callback from browser.')

        # receive data from webgl-conformance-tests.html::postFinalResults
        results = self._testServer.get_form_entries()
        groups_total  = int(results['gtotal'])
        groups_pass   = int(results['gpass'])
        groups_fail   = groups_total - groups_pass
        tests_total   = int(results['ttotal'])
        tests_pass    = int(results['tpass'])
        tests_timeout = int(results['ttimeout'])
        tests_fail    = tests_total - tests_pass

        logging.info('WebGLConformance: %d groups pass',   groups_pass)
        logging.info('WebGLConformance: %d groups fail',   groups_fail)
        logging.info('WebGLConformance: %d tests pass',    tests_pass)
        logging.info('WebGLConformance: %d tests fail',    tests_fail)
        logging.info('WebGLConformance: %d tests timeout', tests_timeout)

        # output numbers for plotting by harness
        keyvals = {}
        keyvals['count_tests_pass']    = tests_pass
        keyvals['count_tests_fail']    = tests_fail
        keyvals['count_tests_timeout'] = tests_timeout

        # handle failed groups/urls and apply waivers
        failTestRun = False
        tests_fail_not_waived = 0
        i = 0
        for key in results:
            unquote_key = urllib.unquote_plus(key)
            if unquote_key.startswith('failed_url:'):
                new_key = "waived_url_%03d" % i
                failures = int(results[key])
                url = unquote_key[11:]
                waived_failures = 0
                if url in self.waived_tests:
                    waived_failures = self.waived_tests[url]
                if failures > waived_failures:
                    failTestRun = True
                    tests_fail_not_waived += failures - waived_failures
                    new_key = "failed_url_%03d" % i
                message = url + " : %d failures (%d waived)"\
                                   % (failures, waived_failures)
                keyvals[new_key] = message
                logging.info(new_key + "   " + message)
                i = i+1
        logging.info('WebGLConformance: %d tests fail not waived',
                     tests_fail_not_waived)
        keyvals['count_tests_fail_not_waived'] = tests_fail_not_waived
        self.write_perf_keyval(keyvals)

        # Write transmitted summary to graphics_WebGLConformance/summary.txt
        summary = urllib.unquote_plus(results['summary'])
        logging.info('\n' + summary)
        results_path = os.path.join(self.bindir,
              "../../results/default/graphics_WebGLConformance/summary.txt")
        f = open(results_path, 'w+')
        f.write(summary)
        f.close()

        # If we saw many failures that were not waived raise an error.
        if failTestRun and tests_fail_not_waived > 20:
            raise error.TestFail('Results: saw failures without waivers. ')


