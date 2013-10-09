# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.server import test

class network_WiFi_ChaosConfigFailure(test.test):
    """ Test to grab debugging info about chaos configuration falures. """

    version = 1


    def _save_all_pages(self):
        for page in range(1, ap.get_number_of_pages() + 1):
            ap.navigate_to_page(page)
            ap.save_screenshot()


    def _write_screenshots(self, filename):
        for (i, image) in enumerate(ap.get_all_screenshots):
            path = os.path.join(self.outputdir,
                                filename, '_%d.png' % (i + 1))
            with open(path, 'wb') as f:
                f.write(image.decode('base64'))


    def run_once(self, ap, missing_from_scan=False):
        """ Main entry function for autotest.

        There are three pieces of information we want to grab:
          1.) Screenshot at the point of failure
          2.) Screenshots of all pages
          3.) Stack trace of failure

        @param ap: an APConfigurator object
        @param missing_from_scan: boolean if the SSID was not found in the scan

        """

        if not missing_from_scan:
            self._write_screenshots('config_failure')
            ap.clear_screenshot_list()
        self._save_all_pages()
        self._write_screenshots('final_configuration')
        ap.clear_screenshot_list()

        if not missing_from_scan:
            logging.error('Traceback:\n %s', ap.traceback)
            raise error.TestError('The AP was not configured correctly. Please '
                                  'see the ERROR log for more details.')
        else:
            raise error.TestError('The SSID %s was not found in the scan. '
                                  'Check the screenshots to debug.')
