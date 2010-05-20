# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, shutil
from autotest_lib.client.bin import site_login, site_ui_test
from autotest_lib.client.common_lib import error, site_ui, utils


class graphics_O3DSelenium(site_ui_test.UITest):
    version = 1

    flaky_test_list = ["TestSampleanimated_sceneLarge",
                       "TestSamplebillboardsMedium",
                       "TestSamplegenerate_textureSmall",
                       "TestSampleinstance_overrideMedium",
                       "TestSampleold_school_shadowsMedium",
                       "TestSampleshadow_mapMedium",
                       "TestSamplesimpleviewer_simpleviewerLarge",
                       "TestSampletrends_trendsLarge",
                       "TestSampleGoogleIO_2009_step14exLarge",
                       "TestSampleShader_Test",
                       "TestSampleMultipleClientsLarge",
                       "TestUnitTesttexture_set_testMedium",
                       "TestUnitTestinit_status_testSmall",
                       "TestStressCullingZSort"]


    def setup(self):
        if not os.path.exists(self.srcdir):
            os.mkdir(self.srcdir)
        src_assets_path = os.path.join(self.bindir, 'assets_o3dtgz')
        tgz_file_list = os.listdir(src_assets_path)
        dst_assets_path = os.path.join(self.bindir,
                                       'O3D', 'o3d', 'samples', 'assets')
        for tgz_file in tgz_file_list:
            shutil.copyfile(os.path.join(src_assets_path, tgz_file),
                            os.path.join(dst_assets_path, tgz_file))


    def run_once(self, timeout=300):
        os.chdir(os.path.join(self.bindir, 'O3D', 'o3d'))
        cmd = "python tests/selenium/main.py"
        cmd = cmd + " --referencedir=o3d_assets/tests/screenshots"
        cmd = cmd + " --product_dir=./"
        cmd = cmd + " --screencompare=perceptualdiff"
        cmd = cmd + " --browserpath=../../chrome_wrapper"
        cmd = cmd + " --browser=*googlechrome"
        cmd = cmd + " --screenshotsdir=tests/selenium/screenshots_chrome"
        cmd = cmd + " --java=/usr/local/lib/icedtea6/bin/java"
        cmd = site_ui.xcommand(cmd)
        result = utils.run(cmd, ignore_status = True)

        # Find out total tests.
        report = re.findall(r"([0-9]+) tests run.", result.stdout)
        if not report:
            return error.TestFail('Output missing: total test number unknown!')
        total = int(report[-1])
        # Find out failures.
        report = re.findall(r"([0-9]+) errors.", result.stdout)
        if not report:
            return error.TestFail('Output missing: error number unknown!')
        failures = int(report[-1])
        report = re.findall(r"([0-9]+) failures.", result.stdout)
        if not report:
            return error.TestFail('Output missing: failure number unknown!')
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
