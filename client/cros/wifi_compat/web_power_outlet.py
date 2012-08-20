# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
import urlparse

import web_driver_core_helpers

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'deps',
                             'chrome_test', 'test_src', 'third_party',
                             'webdriver', 'pylib'))

try:
  from selenium import webdriver
except ImportError:
  raise ImportError('Could not locate the webdriver package.  Did you build? '
                    'Are you using a prebuilt autotest package?')

from selenium.common.exceptions import TimeoutException as \
    SeleniumTimeoutException
from selenium.webdriver.support.ui import WebDriverWait


class WebPowerOutlet(web_driver_core_helpers.WebDriverCoreHelpers):

    def __init__(self, power_strip_ip, outlet_number, username, password):
        """Default initializer.

        Args:
          power_strip_ip: string of the IP Address
          outlet_number: integer or string of the outlet number
          username: string of the username of the web outlet
          password: string of the password of the web outlet
        """
        super(WebPowerOutlet, self).__init__()
        self.power_strip_ip = power_strip_ip
        self.username = username
        self.password = password
        self.admin_url = 'http://%s/index.htm' % self.power_strip_ip
        self.outlet_number = str(outlet_number)
        self.outlet_on = 'Switch ON'
        self.outlet_off = 'Switch OFF'

    def __del__(self):
        try:
            self.driver.close()
        except:
            pass

    def _initialize_driver(self):
        """Creates the webdriver object, throws an exception on failure."""
        try:
            self.driver = webdriver.Remote('http://127.0.0.1:9515', {})
        except Exception, e:
            raise RuntimeError('Could not connect to webdriver, have you '
                               'downloaded the prebuild components to the /tmp '
                               'directory in the chroot?  Have you run: '
                               '(outside-chroot) <path to chroot tmp directory>'
                               '/chromium-webdriver-parts/.chromedriver?\n'
                               'Exception message: %s' % str(e))
        self.wait = WebDriverWait(self.driver, timeout=5)

    def _perform_login_if_needed(self):
        """Detects if the current page is the login page and performs login."""
        username_xpath = ('//input[@type="text" and @name="Username"]')
        try:
            self.wait_for_object_by_xpath(username_xpath)
        except SeleniumTimeoutException, e:
            # Must be on the admin page
            return False
        # Otherwise we have to login
        self.set_content_of_text_field_by_xpath(self.username, username_xpath,
                                                abort_check=True)
        self.set_content_of_text_field_by_xpath(
            self.password, '//input[@type="password" and @name="Password"]')
        self.click_button_by_xpath(
            '//input[@type="Submit" and @name="Submitbtn"]')
        return True

    def _set_outlet_state(self, state):
        """Sets the state of the outlet to on or off.

        Args:
          state: True to turn on, False to turn off.
        """
        self._initialize_driver()
        state_string = 'ON' if state else 'OFF'
        state_url = 'http://%s/outlet?%s=%s' % (self.power_strip_ip,
                                                self.outlet_number,
                                                state_string)
        self.driver.get(state_url)
        if self._perform_login_if_needed():
            self.driver.get(state_url)
        self.driver.close()

    def get_outlet_state(self):
        """Returns if the outlet is on or off.

        Returns:
          True if on, False if off.
        """
        self._initialize_driver()
        self.driver.get(self.admin_url)
        self._perform_login_if_needed()
        outlet_html = 'outlet?%s=' % self.outlet_number
        text = self.wait_for_object_by_xpath(str('//a[contains(@href, "%s")]' %
                                                 outlet_html)).text
        self.driver.close()
        # This is reversed because when the outlet is on the link is Switch OFF
        # and vice versa.
        return text == self.outlet_off

    def turn_on_outlet(self):
        """Turns on the outlet."""
        if not self.get_outlet_state():
            self._set_outlet_state(True)
        if not self.get_outlet_state():
            raise RuntimeError('Unable to turn on the outlet %s on power strip '
                               'with IP %s' % (self.outlet_number,
                                               self.power_strip_ip))

    def turn_off_outlet(self):
        """Turns off the outlet."""
        if self.get_outlet_state():
            self._set_outlet_state(False)
        if self.get_outlet_state():
            raise RuntimeError('Unable to turn off the outlet %s on power '
                               'strip with IP %s' % (self.outlet_number,
                                                     self.power_strip_ip))
