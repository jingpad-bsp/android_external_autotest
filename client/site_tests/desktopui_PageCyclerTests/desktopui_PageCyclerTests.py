# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import commands, logging, os, shutil, time
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error, site_httpd, site_ui
from page_cycler_results_parser import PageCyclerResultsParser


class desktopui_PageCyclerTests(test.test):
    version = 1
    results = {}

    def setup(self, tarball='page_cycler.tar.gz'):
      if os.path.exists(self.srcdir):
        utils.run('rm -rf %s' % self.srcdir)
      tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
      utils.extract_tarball_to_dir(tarball, self.srcdir)
      page_cycler_dir = os.environ['SYSROOT'] + '/usr/local/autotest-chrome/out/Release'
      utils.run('cp %s/page_cycler_tests %s/' % (page_cycler_dir, self.srcdir))
      utils.run('cp %s/setup_test_links.sh %s/' % (page_cycler_dir, self.srcdir))

    def run_page_cycler(self, test_binary_dir, gtest_filter, iters):
        # TODO: Disable screensaver?
        assert(gtest_filter != ''), gtest_filter+' cannot be empty!'
        cmd = '%s/%s' % (test_binary_dir, 'page_cycler_tests')
        cmd = cmd + ' --page-cycler-iterations=' + iters + ' --gtest_filter=' \
        + gtest_filter
        xcmd = site_ui.xcommand(cmd)
        logging.debug('Running: '+xcmd)
        output = utils.system_output(xcmd)
        logging.debug('\n*****************\n')
        logging.debug(output)
        logging.debug('\n*****************\n')
        pcrp = PageCyclerResultsParser()
        result = pcrp.parse_results(output)
        logging.debug(result)
        self.results[gtest_filter] = result

    def run_once(self, iters=10, args=[]):
        # Use a smaller input set for testing purposes, if needed:
###        testNames=['PageCyclerTest.MozFile']
        testNames=['PageCyclerTest.Alexa_usFile', 'PageCyclerTest.MozFile',
            'PageCyclerTest.Intl1File', 'PageCyclerTest.Intl2File',
            'PageCyclerTest.DhtmlFile', 'PageCyclerTest.Moz2File',
            'PageCyclerTest.BloatFile', 'PageCyclerTest.DomFile',
            'PageCyclerTest.MorejsFile', 'PageCyclerTest.MorejsnpFile']

        # Copy the page_cycler binary and link other binaries in a dir.
        output = utils.system_output('pwd')
        logging.debug(output)
        utils.system(self.srcdir + '/setup_test_links.sh')
        # Make page_cycler think it is in the Chrome source dir.
        utils.system('mkdir ' + self.srcdir + '/base')
        utils.system('touch ' + self.srcdir + '/base/base_paths_posix.cc')
        os.chdir(self.srcdir)

        test_binary_dir = self.srcdir

        logging.debug('printing args')
        logging.debug(args)
        logging.debug('printing iters')
        logging.debug(iters)
        for testName in testNames:
            self.run_page_cycler(test_binary_dir, testName, iters)
        self.write_perf_keyval(self.results)
