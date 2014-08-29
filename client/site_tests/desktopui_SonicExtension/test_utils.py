# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import json
import os
import time

import selenium

from extension_pages import e2e_test_utils
from extension_pages import options


class TestUtils(object):
    """Contains all the helper functions for Chrome mirroring automation."""

    short_wait_secs = 3
    step_timeout_secs = 60

    def __init__(self):
        """Constructor"""


    def set_mirroring_options(self, driver, extension_id, settings):
        """Apply all the settings given by the user to the option page.

        @param driver: The chromedriver instance of the test
        @param extension_id: The id of the Cast extension
        @param settings: The settings and information about the test
        """
        options_page = options.OptionsPage(driver, extension_id)
        options_page.open_hidden_options_menu()
        time.sleep(self.short_wait_secs)
        for key in settings.keys():
            options_page.set_value(key, settings[key])


    def start_v2_mirroring_test_utils(
            self, driver, extension_id, receiver_ip, url, fullscreen,
            udp_proxy_server=None, network_profile=None):
        """Use test util page to start mirroring session on specific device.

        @param driver: The chromedriver instance
        @param extension_id: The id of the Cast extension
        @param receiver_ip: The ip of the Eureka dongle to launch the activity
        @param url: The URL to navigate to
        @param fullscreen: click the fullscreen button or not
        @param udp_proxy_server: the address of udp proxy server,
            it should be a http address, http://<ip>:<port>
        @param network_profile: the network profile,
            it should be one of wifi, bad and evil.
        @return True if the function finishes
        """
        e2e_test_utils_page = e2e_test_utils.E2ETestUtilsPage(
                driver, extension_id)
        time.sleep(self.short_wait_secs)
        tab_handles = driver.window_handles
        e2e_test_utils_page.receiver_ip_or_name_v2_text_box().set_value(
                receiver_ip)
        e2e_test_utils_page.url_to_open_v2_text_box().set_value(url)
        if udp_proxy_server:
            e2e_test_utils_page.udp_proxy_server_text_box().set_value(
                    udp_proxy_server)
        if network_profile:
            e2e_test_utils_page.network_profile_text_box().set_value(
                    network_profile)
        e2e_test_utils_page.open_then_mirror_v2_button().click()
        all_handles = driver.window_handles
        video_handle = [x for x in all_handles if x not in tab_handles].pop()
        driver.switch_to_window(video_handle)
        self.navigate_to_test_url(driver, url, fullscreen)
        return True


    def stop_v2_mirroring_test_utils(self, driver, extension_id):
      """Use test util page to stop a mirroring session on a specific device.

      @param driver: The chromedriver instance
      @param extension_id: The id of the Cast extension
      @param activity_id: The id of the mirroring activity
      """
      e2e_test_utils_page = e2e_test_utils.E2ETestUtilsPage(driver,
                                                            extension_id)
      e2e_test_utils_page.go_to_page()
      time.sleep(self.short_wait_secs)
      e2e_test_utils_page.stop_v2_mirroring_button().click()


    def start_v2_mirroring_sdk(self, driver, device_ip, url, extension_id):
        """Use SDK to start a mirroring session on a specific device.

        @param driver: The chromedriver instance
        @param device_ip: The IP of the Eureka device
        @param url: The URL to navigate to
        @param extension_id: The id of the Cast extension
        @return True if the function finishes
        @raise RuntimeError for timeouts
        """
        self.set_auto_testing_ip(driver, extension_id, device_ip)
        self.nagviate(driver, url, False)
        time.sleep(self.short_wait_secs)
        driver.execute_script('loadScript()')
        self._wait_for_result(
                lambda: driver.execute_script('return isSuccessful'),
                'Timeout when initiating mirroring... ...')
        driver.execute_script('startV2Mirroring()')
        self._wait_for_result(
                lambda: driver.execute_script('return isSuccessful'),
                'Timeout when triggering mirroring... ...')
        return True


    def stop_v2_mirroring_sdk(self, driver, activity_id=None):
        """Use SDK to stop the mirroring activity in Chrome.

        @param driver: The chromedriver instance
        @param activity_id: The id of the mirroring activity
        @raise RuntimeError for timeouts
        """
        driver.execute_script('stopV2Mirroring()')
        self._wait_for_result(
                lambda: driver.execute_script('return isSuccessful'),
                self.step_timeout_secs)


    def set_auto_testing_ip(self, driver, extension_id, device_ip):
        """Set the auto testing IP on the extension page.

        @param driver: The chromedriver instance
        @param extension_id: The id of the Cast extension
        @param device_ip: The IP of the device to test against
        """
        e2e_test_utils_page = e2e_test_utils.E2ETestUtilsPage(
                driver, extension_id)
        e2e_test_utils_page.execute_script(
                'localStorage["AutoTestingIp"] = "%s";' % device_ip)


    def upload_v2_mirroring_logs(self, driver, extension_id):
        """Uploads v2 mirroring logs for the latest mirroring session.

        @param driver: The chromedriver instance of the browser
        @param extension_id: The extension ID of the Cast extension
        @return The report id in crash staging server.
        @raises RuntimeError if an error occurred during uploading
        """
        e2e_test_utils_page = e2e_test_utils.E2ETestUtilsPage(
                driver, extension_id)
        e2e_test_utils_page.go_to_page()
        time.sleep(self.short_wait_secs)
        e2e_test_utils_page.upload_v2_mirroring_logs_button().click()
        report_id = self._wait_for_result(
            e2e_test_utils_page.v2_mirroring_logs_scroll_box().get_value,
            'Failed to get v2 mirroring logs')
        if 'Failed to upload logs' in report_id:
          raise RuntimeError('Failed to get v2 mirroring logs')
        return report_id


    def get_chrome_version(self, driver):
        """Return the Chrome version that is being used for running test.

        @param driver: The chromedriver instance
        @return The Chrome version
        """
        get_chrome_version_js = 'return window.navigator.appVersion;'
        app_version = driver.execute_script(get_chrome_version_js)
        for item in app_version.split():
           if 'Chrome/' in item:
              return item.split('/')[1]
        return None


    def get_chrome_revision(self, driver):
        """Return Chrome revision number that is being used for running test.

        @param driver: The chromedriver instance
        @return The Chrome revision number
        """
        get_chrome_revision_js = ('return document.getElementById("version").'
                                  'getElementsByTagName("span")[2].innerHTML;')
        driver.get('chrome://version')
        return driver.execute_script(get_chrome_revision_js)


    def get_extension_id_from_flag(self, extra_flags):
        """Get the extension ID based on the whitelisted extension id flag.

        @param extra_flags: A string which contains all the extra chrome flags
        @return The ID of the extension. Return None if nothing is found.
        """
        extra_flags_list = extra_flags.split()
        for flag in extra_flags_list:
            if 'whitelisted-extension-id=' in flag:
                return flag.split('=')[1]
        return None


    def navigate_to_test_url(self, driver, url, fullscreen):
        """Navigate to a given URL. Click fullscreen button if needed.

        @param driver: The chromedriver instance
        @param url: The URL of the site to navigate to
        @param fullscreen: True and the video will play in full screen mode.
                           Otherwise, set to False
        """
        driver.get(url)
        driver.refresh()
        if fullscreen:
          self.request_full_screen(driver)


    def request_full_screen(self, driver):
        """Requests full screen.

        @param driver: The chromedriver instance
        """
        try:
            time.sleep(self.short_wait_secs)
            driver.find_element_by_id('fsbutton').click()
        except selenium.common.exceptions.NoSuchElementException as error_message:
            print 'Full screen button is not found. ' + str(error_message)


    def _wait_for_result(self, get_result, error_message):
        """Waits for the result.

        @param get_result: the function to get result.
        @param error_message: the error message in the exception
            if it is failed to get result.
        @return The result.
        @raises RuntimeError if it is failed to get result within
            self.step_timeout_secs.
        """
        start = time.time()
        while (((time.time() - start) < self.step_timeout_secs)
               and not get_result()):
            time.sleep(self.step_timeout_secs/10.0)
        if not get_result():
            raise RuntimeError(error_message)
        return get_result()


    def set_focus_tab(self, driver, tab_handle):
      """Set the focus on a tab.

      @param driver: The chromedriver instance
      @param tab_handle: The chrome driver handle of the tab
      """
      driver.switch_to_window(tab_handle)
      driver.get_screenshot_as_base64()


    def block_setup_dialog(self, driver, extension_id):
        """Tab cast through the extension.

        @param driver: A chromedriver instance that has the extension loaded.
        @param extension_id: Id of the extension to use.
        """
        e2e_test_utils_page = e2e_test_utils.E2ETestUtilsPage(
                driver, extension_id)
        e2e_test_utils_page.go_to_page()
        time.sleep(self.short_wait_secs)
        driver.execute_script(
            'localStorage["blockChromekeySetupAutoLaunchOnInstall"] = "true"')


    def close_popup_tabs(self, driver):
        """Close any popup windows the extension might open by default.

        Since we're going to handle the extension ourselves all we need is
        the main browser window with a single tab. The safest way to handle
        the popup however, is to close the currently active tab, so we don't
        mess with chromedrivers ui debugger.

        @param driver: Chromedriver instance.
        @raises Exception If you close the tab associated with
            the ui debugger.
        """
        # TODO: There are several, albeit hacky ways, to handle this popup
        # that might need to change with different versions of the extension
        # until the core issue is resolved. See crbug.com/338399.
        current_tab_handle = driver.current_window_handle
        for handle in driver.window_handles:
            if current_tab_handle != handle:
                try:
                    driver.switch_to_window(handle)
                    driver.close()
                except:
                    pass
        driver.switch_to_window(current_tab_handle)


    def output_dict_to_file(self, dictionary, file_name,
                               path=None, sort_keys=False):
        """Ouput a dictionary into a file.

        @param dictionary: The dictionary to be output as JSON
        @param file_name: The name of the file that is being output
        @param path: The path of the file. The default is None
        @param sort_keys: Sort dictionary by keys when output. False by default
        """
        if path is None:
            path = os.path.abspath(os.path.dirname(__file__))
        # if json file exists, read the existing one and append to it
        json_file = os.path.join(path, file_name)
        if os.path.isfile(json_file) and dictionary:
            with open(json_file, 'r') as existing_json_data:
                json_data = json.load(existing_json_data)
            dictionary = dict(json_data.items() + dictionary.items())
        output_json = json.dumps(dictionary, sort_keys=sort_keys)
        with open(json_file, 'w') as file_handler:
            file_handler.write(output_json)
