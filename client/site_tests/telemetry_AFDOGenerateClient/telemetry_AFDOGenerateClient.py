# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Run a pre-defined set of pages on the DUT for Chrome profile collection.

The purpose of this test is to exercise chrome with a meaningful set
of pages while a profile of Chrome is captured. It also aims at using
the minimum set of functionality from Telemetry since Telemetry is not
very stable on ChromeOS at this point.

This test is designed to be called from the telemetry_AFDOGenerate
server test. The server test will start the "perf" profiling tool on
the DUT before starting this test. It will also capture the chrome
profile and upload it to Google Storage to be used for an optimized
build of Chrome.
"""

import logging
import os

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.bin import test
from autotest_lib.client.cros import httpd

# List of page cycler pages to use for Chrome profiling
PAGE_CYCLER_BENCHMARKS = [
        'alexa_us',
        'bloat',
        'dhtml',
        'dom',
        'intl1',
        'intl2',
        'morejs',
        'morejsnp',
        'moz',
        'moz2' ]

HTTP_PORT = 8000
FILE_URL_PREFIX = 'http://localhost:%d/test_src/' % HTTP_PORT

class telemetry_AFDOGenerateClient(test.test):
    """
    Run a set of pre-defined set of pages to exercise Chrome so that
    we can capture a Chrome profile.
    """
    version = 1


    def initialize(self):
        """Setup required DEPS and start the http listener."""
        dep = 'page_cycler_dep'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)

        try:
            self.listener = httpd.HTTPListener(HTTP_PORT, docroot=dep_dir)
            self.listener.run()
        except Exception as err:
            logging.info('Timeout starting HTTP listener')
            raise error.TestFailRetry(err)


    def cleanup(self):
        """Stop the active http listener."""
        self.listener.stop()


    def run_once(self):
        """Display predetermined set of pages so that we can profile Chrome."""
        with chrome.Chrome() as cr:
            for benchmark in PAGE_CYCLER_BENCHMARKS:
                self._navigate_page_cycler(cr, benchmark)


    def _navigate_page_cycler(self, cr, benchmark):
        """Navigate to a specific page_cycler page.

        Navigates to the specified page_cycler and waits for the value
        of the __pc_done cookie to indicate it is done.

        @param cr: instance of chrome.Chrome class to control chrome.
        @param benchmark: page_cycler page to display.
        """

        PC_START_PAGE = 'data/page_cycler/%s/start.html?auto=1'
        PC_DONE_EXP = 'window.document.cookie.indexOf("__pc_done=1") >= 0'
        tab = cr.browser.tabs.New()
        tab.Activate()
        benchmark_start_page = PC_START_PAGE % benchmark
        logging.info('Navigating to page cycler %s', benchmark)
        tab.Navigate(FILE_URL_PREFIX + benchmark_start_page)
        tab.WaitForDocumentReadyStateToBeComplete()
        tab.WaitForJavaScriptExpression(PC_DONE_EXP, 600)
        logging.info('Completed page cycler %s', benchmark)
        tab.Close()
