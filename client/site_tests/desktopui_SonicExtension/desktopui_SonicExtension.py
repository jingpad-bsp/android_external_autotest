# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import json
import time

import common

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chromedriver
from autotest_lib.client.cros import httpd


class desktopui_SonicExtension(test.test):
    """Test loading the sonic extension through chromedriver."""
    version = 1
    cast_delay = 20
    dep = 'sonic_extension'


    def _install_sonic_extension(self):
        dep_dir = os.path.join(self.autodir, 'deps', self.dep)
        logging.info('Installing sonic extension into %s', dep_dir)
        self.job.install_pkg(self.dep, 'dep', dep_dir)
        return dep_dir


    def _check_manifest(self, extension_path):
        """Checks the manifest for a public key.

        The sonic extension is an autotest dependency and will get
        installed through install_pkg as a component extension (with
        a public key). Any other method of installation is supported
        too, as long as it has a public key.

        @param extension_path: A path to the directory of the extension
            that contains a manifest.json.

        @raises TestError: If the extension doesn't have a public key.
        """
        manifest_json_file = os.path.join(extension_path, 'manifest.json')
        with open(manifest_json_file, 'r') as f:
            manifest_json = json.loads(f.read())
            if not manifest_json.get('key'):
                raise error.TestError('Not a component extension, cannot '
                                      'proceed with sonic test')


    def tab_cast(self, driver, chromecast_ip, extension_id):
        """Tab cast through the extension.

        @param driver: A chromedriver instance that has the chromecast
            extension loaded.
        @param chromecast_ip: The ip of the chromecast device to cast to.
        @param extension_id: Id of the extension to use.
        """
        extension_url = 'chrome-extension://%s' % extension_id
        driver.get('%s/%s' % (extension_url, self._test_utils_page))
        if driver.title != self._test_utils_title:
            raise error.TestError('Getting title failed, got title: %s'
                                  % driver.title)
        driver.find_element_by_id('receiverIpAddress').send_keys(
                chromecast_ip)

        logging.info('Attempting to cast %s', self._test_url)
        driver.find_element_by_id('urlToOpen').send_keys(self._test_url)
        driver.find_element_by_id('mirrorUrl').click()


    def initialize(self, extension_dir=None, live=False):
        """Initialize the test.

        @param extension_dir: Directory of a custom extension.
            If one isn't supplied, the latest ToT extension is
            downloaded and loaded into chromedriver.
        @param live: Use a live url if True. Start a test server
            and server a hello world page if False.
        """
        super(desktopui_SonicExtension, self).initialize()

        if not extension_dir:
            extension_path = self._install_sonic_extension()
        else:
            extension_path = os.path.join(self.autodir, 'tests',
                                          'desktopui_SonicExtension',
                                          extension_dir)
        if not os.path.exists(extension_path):
            raise error.TestError('Failed to install sonic extension.')
        self._check_manifest(extension_path)
        self._extension_path = extension_path
        self._test_utils_page = 'e2e_test_utils.html'
        self._test_utils_title = 'Google Cast extension E2E test utilities'
        self._whitelist_id = 'enhhojjnijigcajfphajepfemndkmdlo'

        if live:
            self._test_url = 'http://www.google.com'
            self._test_server = None
        else:
            self._test_url = 'http://localhost:8000/hello.html'
            self._test_server = httpd.HTTPListener(8000, docroot=self.bindir)
            self._test_server.run()


    def cleanup(self):
        """Clean up the test environment, e.g., stop local http server."""
        if self._test_server:
            self._test_server.stop()
        super(desktopui_SonicExtension, self).cleanup()


    def _close_popups(self, driver):
        """Close any popup windows the extension might open by default.

        Since we're going to handle the extension ourselves all we need is
        the main browser window with a single tab. The safest way to handle
        the popup however, is to close the currently active tab, so we don't
        mess with webdrivers ui debugger.

        @param driver: Chromedriver instance.

        @raises WebDriverException: If you close the tab associated with
            the ui debugger.
        """
        # TODO: There are several, albeit hacky ways, to handle this popup
        # that might need to change with different versions of the extension
        # until the core issue is resolved. See crbug.com/338399.
        if len(driver.window_handles) > 1:
            driver.close()
        driver.switch_to_window(driver.window_handles[0])


    def run_once(self, chromecast_ip):
        """Run the test code."""

        # TODO: When we've cloned the sonic test repo get these from their
        # test config files.
        logging.info('Starting sonic client test.')
        kwargs = {
            'extension_paths' : [self._extension_path],
            'is_component' : True,
            'extra_chrome_flags': ['--no-proxy-server', '--start-maximized',
                                   '--disable-web-security',
                                   '--enable-experimental-extension-apis',
                                   '--enable-logging=stderr', '--v=2',
                                   ('--whitelisted-extension-id=%s' %
                                    self._whitelist_id)],
        }

        with chromedriver.chromedriver(**kwargs) as chromedriver_instance:
            driver = chromedriver_instance.driver
            self._close_popups(driver)
            extension = chromedriver_instance.get_extension(
                          self._extension_path)
            logging.info('Starting tabcast to extension: %s',
                         extension.extension_id)
            self.tab_cast(driver, chromecast_ip, extension.extension_id)
            time.sleep(self.cast_delay)
            screenshot_file = 'sonic_screenshot'
            utils.take_screenshot(self.resultsdir, screenshot_file)
            logging.info('Screenshot of cast extension saved to %s',
                         os.path.join(self.resultsdir, screenshot_file))

