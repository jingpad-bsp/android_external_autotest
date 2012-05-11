# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, shutil
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui, graphics_ui_test

class graphics_O3DSelenium(graphics_ui_test.GraphicsUITest):
    version = 1

    flaky_test_list = ["TestSampleanimated_sceneLarge",
                       "TestSamplebillboardsMedium",
                       "TestSampleconvolutionMedium",
                       "TestSamplegenerate_textureSmall",
                       "TestSampleinstance_overrideMedium",
                       "TestSamplejugglerMedium",
                       "TestSamplesobelMedium",
                       "TestSampleold_school_shadowsMedium",
                       "TestSampleshadow_mapMedium",
                       "TestSamplesimpleviewer_simpleviewerLarge",
                       "TestSampletrends_trendsLarge",
                       "TestSamplezsortingMedium",
                       "TestSampleGoogleIO_2009_step14exLarge",
                       "TestSampleShader_Test",
                       "TestSampleMultipleClientsLarge",
                       "TestUnitTesttexture_set_testMedium",
                       "TestUnitTestinit_status_testSmall",
                       "TestStressCullingZSort"]


    def setup(self, tarball='o3d-tests-0.0.1.tar.bz2'):
        if not os.path.exists(self.srcdir):
            os.mkdir(self.srcdir)

        dst_path = os.path.join(self.bindir, 'O3D')
        tarball_path = os.path.join(self.bindir, tarball)
        if not os.path.exists(dst_path):
            if not os.path.exists(tarball_path):
                utils.get_file(
                    'http://commondatastorage.googleapis.com/chromeos-localmirror/distfiles/' + tarball,
                    tarball_path)
            utils.extract_tarball_to_dir(tarball_path, dst_path)

        src_assets_path = os.path.join(self.bindir, 'assets_o3dtgz')
        tgz_file_list = os.listdir(src_assets_path)
        dst_assets_path = os.path.join(self.bindir,
                                       'O3D', 'o3d', 'samples', 'assets')
        for tgz_file in tgz_file_list:
            shutil.copyfile(os.path.join(src_assets_path, tgz_file),
                            os.path.join(dst_assets_path, tgz_file))


    def run_once(self, timeout=300):
        os.chdir(os.path.join(self.bindir, 'O3D', 'o3d'))
        # Pick any of these that exists. We probably don't want a generic
        # search for ANY java, and such is not even possible at this time
        #(java-config -J).
        java_paths = [
            "/usr/local/lib/icedtea6/bin/java",
            "/usr/local/opt/icedtea6-bin-1.6.2/bin/java",
            "" ]
        for java_bin in java_paths:
          if os.path.exists(java_bin):
            break
        # Selenium main will hang forever if --java argument !exists; fail
        # before that happens.
        if java_bin == "":
          raise error.TestFail('Missing java interpreter!')
        cmd = "python tests/selenium/main.py"
        cmd = cmd + " --referencedir=o3d_assets/tests/screenshots"
        cmd = cmd + " --product_dir=./"
        cmd = cmd + " --screencompare=perceptualdiff"
        cmd = cmd + " --browserpath=../../chrome_wrapper"
        cmd = cmd + " --browser=*googlechrome"
        cmd = cmd + " --screenshotsdir=tests/selenium/screenshots_chrome"
        cmd = cmd + " --java=" + java_bin
        cmd = cros_ui.xcommand(cmd)
        result = utils.run(cmd, ignore_status = True)

        # Find out total tests.
        report = re.findall(r"([0-9]+) tests run.", result.stdout)
        if not report:
            raise error.TestFail('Output missing: total test number unknown!')
        total = int(report[-1])
        # Find out failures.
        report = re.findall(r"([0-9]+) errors.", result.stdout)
        if not report:
            raise error.TestFail('Output missing: error number unknown!')
        failures = int(report[-1])
        report = re.findall(r"([0-9]+) failures.", result.stdout)
        if not report:
            raise error.TestFail('Output missing: failure number unknown!')
        failures += int(report[-1])
        logging.info('RESULTS: %d out of %d tests failed!', failures, total)

        # If all failed cases belong to flaky_test_list, we still pass the test.
        report = re.findall(r"SELENIUMRESULT ([a-zA-Z_0-9]+) "
                            r"\([a-zA-Z_0-9]+\.[a-zA-Z_0-9]+\) "
                            r"<\*googlechrome> \[[0-9.s]+\]: FAIL",
                            result.stdout)
        ignored_failures = 0
        error_message = "Unexpected failure cases:"
        for report_item in report:
            if report_item in self.flaky_test_list:
                ignored_failures += 1
                logging.info("FAILURE (ignored): %s" % report_item)
            else:
                error_message += " " + report_item

        if failures > ignored_failures:
            raise error.TestFail(error_message)
