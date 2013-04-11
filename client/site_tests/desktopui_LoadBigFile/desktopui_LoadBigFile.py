# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, httpd


class desktopui_LoadBigFile(cros_ui_test.UITest):
    version = 1


    def initialize(self):
        super(desktopui_LoadBigFile, self).initialize(creds='$default')
        # Create a large file
        working_folder = os.path.dirname(os.path.abspath(__file__))
        big_file_path = os.path.join(working_folder, 'bigfile.txt')
        if os.path.exists(big_file_path):
            os.remove(big_file_path)
        file_handle = open(big_file_path, 'w')
        # Devices with 2GB of RAM can't load a page with a million lines within
        # a reasonable amount of time.
        multiplier = 1
        chromeos_board = self.pyauto.ChromeOSBoard()
        if chromeos_board == 'stumpy' or chromeos_board == 'lumpy':
            multiplier = 2
        for i in xrange(500000 * multiplier):
            file_handle.write('large amount of data that is irrelevant.\n')
        file_handle.write('End of The Project\n')
        file_handle.flush()
        file_handle.close()
        self._test_url = 'http://localhost:8000/bigfile.txt'
        self._expected_title = 'bigfile.txt'
        self._sanity_test_url = 'http://localhost:8000/hello.html'
        self._sanity_expected_title = 'Hello World'
        self._testServer = httpd.HTTPListener(8000, docroot=self.bindir)
        self._testServer.run()


    def cleanup(self):
        self._testServer.stop()
        super(desktopui_LoadBigFile, self).cleanup()


    def run_once(self):
        import pyauto_errors

        def _OpenUrl():
            self.pyauto.NavigateToURL(self._sanity_test_url)
            tab_title = self.pyauto.GetActiveTabTitle()
            logging.info('Expected tab title: %s. Got: %s' %
                         (self._sanity_expected_title, tab_title))
            return tab_title == self._sanity_expected_title

        utils.poll_for_condition(
            _OpenUrl,
            error.TestError('The sanity tab failed to open %s' %
                            self._sanity_test_url),
            timeout = 60,
            sleep_interval=1)
        # Currently the ActionTimeoutChanger does not work.  Once it works we
        # can increase the timeout and keep the size of the file static.
        # See bug http://crbug.com/139926
        # pyauto_timeout_changer = self.pyauto.ActionTimeoutChanger(
        #     self.pyauto, 240 * 1000)
        try:
            self.pyauto.NavigateToURL(self._test_url)
        except pyauto_errors.JSONInterfaceError as e:
            raise error.TestError('The big file did not load.  Error: %s' %
                                  str(e))
        # del pyauto_timeout_changer
        find_results = self.pyauto.FindInPage('End of The Project')
        if find_results['match_count'] != 1:
            error.TestError('Could not find text at the end of the file.  '
                            'The page did not load correctly.')
